# Python installation

This project is built using python version 3.x. You can download the latest version of python from - https://www.python.org/downloads/macos/

# Requirements

To install the python packages required for this project, run:

`pip3 install -r requirements.txt`

This project requires a Cerbero API Key and extracts the key from `CEREBRO_API_KEY` environment variable.

# How to run

`dependency_graph_builder.py` takes the following command line arguments:
- `--product_filter` - Filter projects by Product(s). Example: Foundation
- `--category_filter` - Filter projects by Categories(s). Example: Infrastructure,Service
- `--project_permalink` - Determines which project you want to build the dependency graph for. Filters on project permalink. Example: kubernetes
- `--graph_type` - Determines the type of dependency to graph to build. Expected values are: uses or usedby
- `--max_depth` - Determines the maximum depth to build dependencies for a given project. Defaults to 2
- `--export_to_json` - Determines if dependency data is to be exported to JSON. Default is 'N'
- `--export_to_plain_english` - Determines if dependency data is to be formatted in "plain english" and exported to a TXT file. Default is 'N'

Examples:

Render a uses dependency graph for the kubernetes project:
```python3 dependency_graph_builder.py --product_filter="Foundation" --category_filter="Unknown,Infrastructure,Internal Tool,Library,External Service,Service" --project_permalink=kubernetes --graph_type=uses --max_depth=3```


Render a uses dependency graph for the kubernetes project and export all data formatted from Cerebro to JSON and TXT
```python3 dependency_graph_builder.py --project_permalink=kubernetes --graph_type=uses --max_depth=3 --export_to_json=Y --export_to_plain_english=Y```

