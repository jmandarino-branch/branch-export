# python 2.7
import ast
import errno
import datetime
import json
import os
import re
import sys

from collections import OrderedDict
import pandas as pd
import pytz
from sqlalchemy.engine import create_engine
import unicodecsv as csv  # much easier https://stackoverflow.com/a/31642070

dfs = create_engine('presto://presto.prod.branch.io:80/hive/dfs_prod')


## Helpful urls
# https://branch.atlassian.net/wiki/spaces/DATAP/pages/746225683/Manually+exporting+segments

class Settings:
    """An object to hold all the data for the settings of this script

    Stores all the data from the settings.json file accessed in one place. Valid Timezones can be found in pytz
    https://gist.github.com/heyalexej/8bf688fd67d7199be4a1682b3eec7568

    input_file (str): the filename we want to parse
    output_file (str): the file name we want to write to
    default_timezone (str): the timezone the data starts in
    output_timezone: the timezone to convert data into
    app_id: (int) the Branch App Id
    """

    def __init__(self, input_file=None, output_file=None, default_timezone='UTC', output_timezone=None,
                 custom_column_headers=[], app_id=None):
        self.input_file_path = input_file
        self.output_file_path = output_file
        self.default_timezone = default_timezone
        self.output_timezone = output_timezone
        self.custom_column_headers = custom_column_headers
        self.app_id = app_id


def import_settings(path_to_settings=None):
    """Creates a settings object by reading the settings file

    :param path_to_settings: String of file path
    :return: Settings Obj
    """

    file_path = 'settings.json' if path_to_settings is None else path_to_settings

    if not os.path.isfile(file_path):
        # settings file doesn't exist
        raise IOError(errno.ENOENT, os.strerror(errno.ENOENT), 'settings.json')

    with open(file_path) as in_file:
        data = json.load(in_file)
        settings =   Settings()

        # required attributes, fail if missing
        try:
            settings.input_file_path = os.path.join(os.path.dirname(sys.argv[0]), data['input_folder'], data['input_file'])
            settings.output_file_path = os.path.join(os.path.dirname(sys.argv[0]), data['output_folder'], data['output_file'])
            settings.default_timezone = data['default_timezone']
            settings.output_timezone = data['output_timezone']
            settings.custom_column_headers = data.get('custom_column_headers', [])
            settings.app_id = data['app_id']
        except KeyError as e:
            print("Key not found in {}: ".format(file_path) + str(e))
            sys.exit(1)

    return settings


def get_db_data(selected_columns, app_id, y, m, d):
    """Run a SQL Query to download data from Presto

    :param selected_columns: [list] a list of strings of the names of the columns to select
    :param app_id: Branch Dashboard app id
    :param y: (int) year  to query
    :param m: (int) month to query
    :param d: (int) day to query
    :return: (Dataframe obj) the result of the query
    """
    # TODO edit string based on what query to run
    query_string = "select {} from hive.dfs_prod.eo_custom_event where app_id={} and y={} and m={} and d={}".format(
        ', '.join(selected_columns), app_id, y, m, d)
    return pd.read_sql(query_string, con=dfs)


def escape_single_quotes(custom_data):
    """edit the title_name of the custom_data columns dictionary

    :param custom_data: a dictionary of data from the custom_data
    :return: edited custom data
    """
    # https://stackoverflow.com/questions/10569438/how-to-print-unicode-character-in-python
    # https://regex101.com/r/nM4bXf/1
    if re.search("(?<!u)'(?!:|}|,)", custom_data.get('title_name', '')):
        z = re.sub(r"(?<!u)'(?!:|}|,)", '\\\'', custom_data.get('title_name', None))

        custom_data['title_name'] = z
        return custom_data
    return custom_data


def dataframe_to_csv(settings, dataframe):
    """Take a Pandas dataframe and export it to CSV

    :param settings: (Settings obj) the settings object defined at the start
    :param dataframe:
    :return:
    """
    if not os.path.exists(settings.input_file_path):
        raise IOError("'input_file_path' not defined in settings object")
    dataframe['custom_data'].apply(escape_single_quotes)
    dataframe.to_csv(settings.input_file_path, header=True, encoding='utf-8', index=False)


def parse_csv(settings):
    with open(settings.input_file_path) as csv_file:
        csv_reader = csv.DictReader(csv_file, delimiter=',')

        csv_headers = csv_reader.fieldnames
        # if custom_column headers exist add them
        if settings.custom_column_headers:
            csv_headers += settings.custom_column_headers

        write_csv(settings, csv_headers, 'w') # write header

        for row in csv_reader:
            d = OrderedDict()

            # copy values into an ordered dictionary. in python 2.7 dictionaries aren't ordered (row is useless)
            for col_name in csv_headers:
                d[col_name] = row.get(col_name, None)

            # convert timezone to Timestamp defined in settings obj
            d['timestamp'] = str(convert_timezone(row['timestamp'], settings.default_timezone, settings.output_timezone))
            d['last_attributed_touch_timestamp'] = str(convert_timezone(row['last_attributed_touch_timestamp'], settings.default_timezone, settings.output_timezone))

            # explode data from custom data -- this is specific to each client
            if d['custom_data']:
                # https://stackoverflow.com/a/36599122 -- custom data has single quotes which json.loads doesn't support
                data = ast.literal_eval(d['custom_data'])


                d['title_id'] = data.get('title_id', None)
                d['title_name'] = data.get('title_name', None)
                d['genre_type'] = data.get('genre_type', None)
                d['episode_no'] = data.get('episode_no', None)
                d['purchase_type'] = data.get('purchase_type', None)
                d['purchase_quantity'] = data.get('purchase_quantity', None)
                d['purchase_list'] = data.get('purchase_list', None)


            write_csv(settings, d.values(), 'a')


def write_csv(settings, row, mode):
    """A wrapper for csv.writer method

    :param settings: (settings obj) a reference to the settings object
    :param row: a list of items to write
    :param mode: file mode as defined by python, should be 'w' or 'a'
    :return: None
    """
    with open(settings.output_file_path, mode=mode) as csv_file:
        csv_writer = csv.writer(csv_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        csv_writer.writerow(row)


def convert_timezone(date_string, initial_timezone, output_timezone):
    """Convert timezones

    :param date_string: string: unix timestamp (in milliseconds) date to convert
    :param initial_timezone: string: pytz timezone value of the date's current timezone
    :param output_timezone: string: pytz timezone value of the timezone to convert to
    :return: (datetime) The datetime object with a appropriate timezone
    """

    if date_string == '':
        return ''
    # should we check to see if string is convertible
    date = datetime.datetime.fromtimestamp(float(date_string)/1000.0, tz=pytz.timezone(initial_timezone))
    return date.astimezone(pytz.timezone(output_timezone))


if __name__ == '__main__':
    # start here
    settings_obj = import_settings()

    # a list of the cols to grab from DB (might be best in settings)
    cols = ['name', 'timestamp', 'last_attributed_touch_timestamp', 'last_attributed_touch_data_tilde_campaign',
            'last_attributed_touch_data_tilde_secondary_publisher', 'last_attributed_touch_data_tilde_ad_set_name',
            'last_attributed_touch_data_tilde_ad_name', 'days_from_last_attributed_touch_to_event', 'user_data_os',
            'first_event_for_user', 'user_data_aaid', 'user_data_idfa', 'user_data_idfv', 'custom_data',
            'last_attributed_touch_type', 'last_attributed_touch_data_custom_fields']
    # get data from DB
    dataframe = get_db_data(cols, settings_obj.app_id, 2019, 8, 3)
    # convert to CSV
    dataframe_to_csv(settings_obj, dataframe)
    # parse csv and write to file
    parse_csv(settings_obj)
