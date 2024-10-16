import argparse
import json
import os
import time

import graphviz
import requests
import re

# Get Cerebro API key from environment variable
CEREBRO_API_KEY = os.getenv('CEREBRO_API_KEY', None)
HEADERS = {
    "Authorization": f"Token {CEREBRO_API_KEY}"
}

def save_to_json(filename, project_data):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, 'w', encoding='utf-8') as json_file:
        json.dump(project_data, json_file, indent=4)

def replace_urls_in_text(text, replacement_text='<URL REDACTED>'):
    url_pattern = re.compile(r'https?://\S+|www\.\S+')
    urls = url_pattern.findall(text)

    for url in urls:
        text = text.replace(url, replacement_text)

    return text

def strip_html_in_text(text):
    html_pattern = re.compile(r'<[^>]+>')
    html_tags = html_pattern.findall(text)

    for html_tag in html_tags:
        text = text.replace(html_tag, '')

    return text

def save_to_plain_english_txt(filename, project_data):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    string_output = []
    for project in project_data:
        # Sanitize data
        
        # Remove hyphens and underscores if name is the same as permalink to make it easier to interpret
        project_name = " ".join(re.sub('[-_]', ' ', project.get('name')).split())
        project_owner = project.get('owner', 'Unknown')

        # Split products array to comma seperated string
        project_products = ','.join(project.get('products')) if any(project.get('products')) else 'Unknown'
        project_tier = project.get('tier')

        # Some project descriptions have html in it - this function strips the html from the description
        project_desc = strip_html_in_text(project.get('description'))

        # Some project descriptions contain urls to github, confluence etc. - this function replaces them with <URL REDACTED>
        project_desc = replace_urls_in_text(project_desc)

        # Write project details to a new line
        string_output.append(f"The project {project_name} is a {project_tier} project.")

        if project.get('alias'):
            project_alias = project.get('alias')
            string_output.append(f"This project is also known as {project_alias}.")

        # Some project descriptions are set to: "Not provided during import (rake core_features:import:csv[file_path])", or "..." - assume these are invalid
        invalid_descriptions = ['Not provided during import (rake core_features:import:csv[file_path])', '...']
        if not project_desc in invalid_descriptions:
            # Some project descriptions are the same as name or permalink - assume this is invalid as it doesn't describe the project
            if project_desc != project.get('permalink') and project_desc != project.get('name'):
                # Write project description to a new line
                string_output.append(f"{project_name} is described as: \"{project_desc}\"")

        # Write product details of the project to a new line
        string_output.append(f"{project_name} comes under the following product(s): {project_products}. This project is owned by the {project_owner} team.")
        
        if any(project.get('uses')):
            for project_dependency in project.get('uses'):
                project_dependency_name = " ".join(re.sub('[-_]', ' ', project_dependency.get('name')).split())
                
                # Write project dependency to a new line
                string_output.append(f"The project {project_name} depends on {project_dependency_name}.")
        
        if any(project.get('used_by')):
            for project_dependent in project.get('uses'):
                project_dependent_name = " ".join(re.sub('[-_]', ' ', project_dependent.get('name')).split())
                
                # Write project dependents to a new line
                string_output.append(f"The project {project_name} is dependent on by {project_dependent_name}.")
              
    with open(filename, 'w') as txt_file:
        for line in string_output:
            txt_file.write(f"{line}\n")

def filter_on_product_category(projects: dict, product_filter: str, category_filter: str):
    filtered_projects = [
        project for project in projects if (
            (product_filter and (any(product in product_filter.strip().lower() for product in project.get('product_names', []))) or len(project.get('product_names')) == 0) or 
            (category_filter and (project.get('category', '').lower() in category_filter.strip().lower() or not project.get('category'))) or
            (not product_filter and not category_filter)  # Return all if no filters are provided
        )
    ]

    return filtered_projects

def fetch_projects_from_cerebro():
    url = "https://cerebro.zende.sk/projects.json"
    query = "includes=dependent_project_dependencies,providing_project_dependencies&inlines=project_stakeholder_owner_name,product_names,project_repository_urls,link_deployment_urls&search[!release_state]=EOL&per_page=9999"
    response = requests.get(url=f'{url}?{query}', headers=HEADERS, timeout=30)
    data = response.json()

    # Get projects and their dependencies from response payload
    projects = data.get('projects', [])
    project_dependencies = data.get('project_dependencies', [])
    
    return projects, project_dependencies

def build_dependency_graph(dot, added_nodes, added_edges, project_list, source_project_nodes, graph_type, max_depth, depth):    
    # Return if traveresed down to max depth of dependency hell
    if depth > max_depth:
        return

    project_edges = []
    
    # Iterate through "source" nodes to build dependency tree. The apple doesn't fall far from the dependency tree of hell.
    for source_project_node in source_project_nodes:
        source_project_id = source_project_node['id']
        source_project_name = source_project_node['permalink']
        source_project_owner = source_project_node['owner']
        
        # Set source node label
        source_node = f'{source_project_name} [{source_project_owner}]'
        
        if source_project_id not in added_nodes:
            dot.node(source_node)
            added_nodes.add(source_project_id)
        
        # Find new edges depending on graph type
        if graph_type == 'uses':
            project_edge_ids = [prj['id'] for prj in source_project_node['uses']]
        else:
            project_edge_ids = [prj['id'] for prj in source_project_node['used_by']]
        
        project_edges = [prj for prj in project_list if prj['id'] in project_edge_ids]

        # Iterate through edges to build dependency graph
        for edge_project_node in project_edges:
            edge_project_id = edge_project_node['id']
            edge_project_name = edge_project_node['permalink']
            edge_project_owner = edge_project_node['owner']
            
            # Set edge node label
            edge_node = f'{edge_project_name} [{edge_project_owner}]'

            if edge_project_id not in added_nodes:
                dot.node(edge_node)
                added_nodes.add(edge_project_id)

            # Build edge between source and edge nodes
            if graph_type == 'uses':
                if (source_project_id, edge_project_id) not in added_edges:
                    dot.edge(source_node, edge_node)
                    added_edges.add((source_node, edge_node))
            else:
                if (edge_project_id, source_project_id) not in added_edges:
                    dot.edge(edge_node, source_node)
                    added_edges.add((edge_node, source_node))

        # Recursively call build_dependency_graph until no more edges are found
        if any(project_edges):
            build_dependency_graph(dot, added_nodes, added_edges, project_list, source_project_nodes=project_edges, graph_type=graph_type,
                                   max_depth=max_depth, depth=depth+1)

def main(input_args):   
    product_filter = input_args.product_filter if input_args.product_filter else ''
    category_filter = input_args.category_filter if input_args.category_filter else '' 
    project_permalink = input_args.project_permalink
    graph_type = input_args.graph_type
    max_depth = input_args.max_depth if input_args.max_depth else 2
    export_to_json = input_args.export_to_json if input_args.export_to_json else 'N'
    export_to_plain_english = input_args.export_to_plain_english if input_args.export_to_plain_english else 'N'

    # I'm telling you what arguments you set...
    print(f"--product_filter set to: {product_filter}")
    print(f"--category_filter set to: {category_filter}")
    print(f"--project_permalink set to: {project_permalink}")
    print(f"--graph_type set to: {graph_type}")
    print(f"--max_depth set to: {max_depth}")
    print(f"--export_to_json set to: {export_to_json}")
    print(f"--export_to_plain_english set to: {export_to_plain_english}")    

    # Validate cerebro API key
    if CEREBRO_API_KEY is None:
        raise ValueError("Error fetching Cerebro API key. Please set CEREBRO_API_KEY environment variable.")

    # Fetch project and their dependencies from Cerebro
    projects, project_dependencies = fetch_projects_from_cerebro()

    # Filter raw data from Cerebro by product_filter and category_filter
    filtered_raw_data = filter_on_product_category(projects, product_filter, category_filter)

    # Iterate through each project and build the final data set (this isn't even my final form yet!)
    final_data_set = []
    for filtered_record in filtered_raw_data:
        final_data_record = {
            "id": filtered_record.get('id'),
            "permalink": filtered_record.get('permalink'),
            "name": filtered_record.get('name'),
            "description": filtered_record.get('description'),
            "alias": filtered_record.get('nickname'),
            "owner": filtered_record.get('project_stakeholder_owner_name'),
            "tier": filtered_record.get('criticality_tier'),
            "products": filtered_record.get('product_names'),
            "weighting": len(filtered_record.get('dependent_project_dependencies_ids')),
            "uses": [],
            "used_by": []
        }

        # Populate project dependencies
        if any(filtered_record.get('dependent_project_dependencies_ids')):
            for dependent_project_dependencies_id in filtered_record.get('dependent_project_dependencies_ids'):
                dependency_project = [project_dependency for project_dependency in project_dependencies if project_dependency.get('id') == dependent_project_dependencies_id]
                if any(dependency_project):
                    # Get dependency project record to get dependency info (we're only interested in dependencies that match the filter criteria)
                    project_dependency_record = filter_on_product_category([project for project in projects if project.get('id') == dependency_project[0].get('providing_project_id')],
                                                                           product_filter, 
                                                                           category_filter)
                    if any(project_dependency_record):
                        final_data_record["uses"].append({
                            "id": project_dependency_record[0].get('id'),
                            "permalink": project_dependency_record[0].get('permalink'),
                            "name": project_dependency_record[0].get('name'),
                            "description": project_dependency_record[0].get('description'),
                            "alias": project_dependency_record[0].get('nickname'),
                            "owner": project_dependency_record[0].get('project_stakeholder_owner_name'),
                            "tier": project_dependency_record[0].get('criticality_tier'),
                            "products": project_dependency_record[0].get('product_names'),
                            "weighting": len(project_dependency_record[0].get('dependent_project_dependencies_ids'))
                        })
        
        # Populate project dependents
        if any(filtered_record.get('providing_project_dependencies_ids')):
            for providing_project_dependencies_id in filtered_record.get('providing_project_dependencies_ids'):
                dependent_project = [project_dependency for project_dependency in project_dependencies if project_dependency.get('id') == providing_project_dependencies_id]
                if any(dependent_project):
                    # Get dependent project record to get dependency info (we're only interested in dependencies that match the filter criteria)
                    project_dependent_record = filter_on_product_category([project for project in projects if project.get('id') == dependent_project[0].get('dependent_project_id')],
                                                                          product_filter, 
                                                                          category_filter)
                    if any(project_dependent_record):
                        final_data_record["used_by"].append({
                            "id": project_dependent_record[0].get('id'),
                            "permalink": project_dependent_record[0].get('permalink'),
                            "name": project_dependent_record[0].get('name'),
                            "alias": project_dependent_record[0].get('nickname'),
                            "description": project_dependent_record[0].get('description'),
                            "owner": project_dependent_record[0].get('project_stakeholder_owner_name'),
                            "tier": project_dependent_record[0].get('criticality_tier'),
                            "products": project_dependent_record[0].get('product_names'),
                            "weighting": len(project_dependent_record[0].get('dependent_project_dependencies_ids'))
                        })

        final_data_set.append(final_data_record)

    if any(final_data_set):
        timestamp = time.strftime("%Y-%m-%d_%H:%M:%S")
        output_file_name = f"./data/project_dependencies"

        if export_to_json == 'Y':
            # Write dependency data to a JSON file
            save_to_json(f"{output_file_name}_{timestamp}.json", final_data_set)

        if export_to_plain_english == 'Y':
            # Format dependency data in "plain english" and write to a TXT file
            save_to_plain_english_txt(f"{output_file_name}_{timestamp}.txt", final_data_set)
                        
        # Filter projects by project_permalink to build the dependency graph
        filtered_projects = [prj for prj in final_data_set if prj['permalink'] == project_permalink.strip()]

        if any(filtered_projects):   
            pdf_file_name = f'./renders/{project_permalink}/{graph_type}-dependency-graph'

            # Initialize and configure Graphviz directed graph
            dot = graphviz.Digraph(name='Component Dependency Graph', strict=True, format='pdf', graph_attr={'rankdir':'LR'}, 
                                   node_attr={'shape':'rectangle','arrowhead':'normal','arrowsize':'0.5','fontname':'Arial','fontsize':'11','style':'filled','color':'lightblue'})

            # Keep track of nodes/edges to avoid duplicates
            added_nodes = set()
            added_edges = set()

            # Do the thing I was created to do! [0_o]
            build_dependency_graph(dot, added_nodes, added_edges, final_data_set, filtered_projects, graph_type, max_depth, 0)
            
            # Generate and save the graph to file
            dot.render(filename=pdf_file_name, view=True)

            print(f"Dependency graph saved to {pdf_file_name}.pdf")
        else:
            print("No projects found that match project permalink.")
    else:
        print("No projects found that match product or category criteria.")
        
# You can only choose the path that I have laid for you...mwahahaha!
def validate_graph_type(graph_type):
    if graph_type not in ['uses', 'usedby']:
        raise argparse.ArgumentTypeError(f"Invalid graph type: {graph_type}. Please enter either 'uses' or 'usedby'.")
    return graph_type

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a dependency graph of Projects")

    parser.add_argument('--product_filter', required=False, type=str, help='Filter projects by Product(s). Example: Foundation')
    parser.add_argument('--category_filter', required=False, type=str, help='Filter projects by Categories(s). Example: Infrastructure,Service')
    parser.add_argument('--project_permalink', required=True, type=str, help='Determines which project you want to build the dependency graph for. Filters on project permalink. Example: kubernetes')
    parser.add_argument('--graph_type', required=True, type=validate_graph_type, help='Determines the type of dependency to graph to build. Expected values are: uses or usedby')
    parser.add_argument('--max_depth', required=True, type=int, help='Determines the maximum depth to build dependencies for a given project. Defaults to 2')
    parser.add_argument('--export_to_json', required=False, type=str, help='Determines if dependency data is to be exported to JSON. Default is N')
    parser.add_argument('--export_to_plain_english', required=False, type=str, help='Determines if dependency data is to be formatted in "plain english" and exported to a TXT file. Default is N')

    args = parser.parse_args()

    # Pass the arguments to the main function
    main(args)