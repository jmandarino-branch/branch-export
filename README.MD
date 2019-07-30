# Python Data Export Script 


## Purpose:
To download data from the Branch DB and convert it into a format that the customer can use

## How to run:
1. download python modules `pip install -r requirements.txt`
2. populate `settings.json`
3. run script `./main.py` or `/path/to/python main.py`

## settings.json

The `settings.json` file stores all the global information that the script uses to run. It will look like this:

```json
{
  "input_folder": "input",
  "output_folder": "output",
  "input_file": "input.csv",
  "output_file": "output.csv",
  "default_timezone": "UTC",
  "output_timezone":"Asia/Seoul",
  "custom_column_headers": ["title_id","title_name","genre_type","episode_no","purchase_type","purchase_quantity","purchase_list"],
  "app_id": 619458676142395401

}
```

- `input_folder` is the folder at the root level of the script where the input will go
- `output_folder` is the folder at the root level where the output will go
- `input_file` is the file name to read from
- `output_file` is the file name to write to (note this will be erased when running the script)
- `default_timezone` is the Timezone the data from the DB will be in
- `output_timezone` is the Timezone you want to convert the data to
- `custom_column_headers` are extra headers you would like to add to the export
- `app_id` is the Branch App ID

**Important:** Supported Timezone names can be found in pytz by running `pytz.all_timezones` or looking online 


## Script directory hierarchy example:

```
├── input
│   └── input.csv
├── output
│   └── output.csv
├── main.py
├── requirements.txt
├── README.MD
└── settings.json
```



