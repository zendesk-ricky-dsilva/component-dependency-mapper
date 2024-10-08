# Python installation

This project is built using python version 3.x. You can download the latest version of python from - https://www.python.org/downloads/macos/

# Requirements

To install the python packages required for this project, run:

`pip3 install -r requirements.txt`

This project requires a Cerbero API Key and extracts the key from `CEREBRO_API_KEY` environment variable.

# How to run

`dependency_graph_builder_v4.py` takes the following command line arguments:
- `--product_filter` - Filter projects by Product(s). Example: Foundation
- `--category_filter` - Filter projects by Categories(s). Example: Infrastructure,Service
- `--project_filter` - Determines which project you want to build the dependency graph for. Filters on project permalink. Example: fdn-inerface-ui
- `--graph_type` - Determines the type of dependency to graph to build. Expected values are: uses or usedby
- `--export_all_data` - Determines if all data (filtered by product and category) is to be exported to JSON. Default is 'N'
- `--max_depth` - Determines the maximum depth to build dependencies for a given project. Defaults to 2

Example:

```python3 dependency_graph_builder_v4.py --product_filter="Foundation" --category_filter="Unknown,Infrastructure,Internal Tool,Library,External Service,Service" --project_filter=fdn-interface-ui --graph_type=uses --export_all_data=N --max_depth=3```

