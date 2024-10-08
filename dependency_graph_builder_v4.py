import argparse
import json
import os

import graphviz
import requests

# Get Cerebro API key from environment variable
CEREBRO_API_KEY = os.getenv("CEREBRO_API_KEY", None)
HEADERS = {
    "Authorization": f"Token {CEREBRO_API_KEY}"
}
WILDCARD = "*"

def save_to_json(file_path, dictionary):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as json_file:
        json.dump(dictionary, json_file, indent=4)

def filter_projects(projects: dict, product_filter: str, category_filter: str):
    # Filter projects by product and category
    
    filtered_projects = [
        project for project in projects if (product_filter != WILDCARD and any(product for product in project.get('product_names') if product.lower() in product_filter.lower())) and 
        (category_filter != WILDCARD and project.get('category','').lower() in category_filter.lower() or not project.get('category')) # We still want to return projects that are not categorized (naughty, naughty!)
    ] 

    return filtered_projects if any(filtered_projects) else projects

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
    final_data_set = []
    
    product_filter = input_args.product_filter
    category_filter = input_args.category_filter
    project_filter = input_args.project_filter
    graph_type = input_args.graph_type
    export_all_data = input_args.export_all_data if input_args.export_all_data else 'N'
    max_depth = input_args.max_depth if input_args.max_depth else 2

    # I'm telling you what arguments you set...
    print(f"--product_filter set to: {product_filter}")
    print(f"--category_filter set to: {category_filter}")
    print(f"--project_filter set to: {project_filter}")
    print(f"--graph_type set to: {graph_type}")
    print(f"--export_all_data set to: {export_all_data}")
    print(f"--max_depth set to: {max_depth}")

    # Validate cerebro API key
    if CEREBRO_API_KEY is None:
        raise ValueError("Error fetching Cerebro API key. Please set CEREBRO_API_KEY environment variable.")

    # Fetch project and their dependencies from Cerebro
    projects, project_dependencies = fetch_projects_from_cerebro()

    # Filter projects by product_filter and category_filter tags
    filtered_projects = filter_projects(projects, product_filter, category_filter)

    # Iterate through each project and build the final data set (this isn't even my final form yet!)
    for filtered_project in filtered_projects:
        final_data_record = {
            "id": filtered_project.get('id'),
            "permalink": filtered_project.get('permalink'),
            "owner": filtered_project.get('project_stakeholder_owner_name'),
            "products": filtered_project.get('product_names'),
            "weighting": len(filtered_project.get('dependent_project_dependencies_ids')),
            "uses": [],
            "used_by": []
        }

        # Populate project dependencies
        if any(filtered_project.get('dependent_project_dependencies_ids')):
            for dependent_project_dependencies_id in filtered_project.get('dependent_project_dependencies_ids'):
                dependency_project = [project_dependency for project_dependency in project_dependencies if project_dependency.get('id') == dependent_project_dependencies_id]
                if any(dependency_project):
                    # Get dependency project record to get dependency info (we're only interested in dependencies that match the filter criteria)
                    project_dependency_record = filter_projects([project for project in projects if project.get('id') == dependency_project[0].get('providing_project_id')],
                                                                product_filter, 
                                                                category_filter)
                    if any(project_dependency_record):
                        final_data_record["uses"].append({
                            "id": project_dependency_record[0].get('id'),
                            "permalink": project_dependency_record[0].get('permalink'),
                            "owner": project_dependency_record[0].get('project_stakeholder_owner_name'),
                            "weighting": len(project_dependency_record[0].get('dependent_project_dependencies_ids'))
                        })
        
        # Populate project dependents
        if any(filtered_project.get('providing_project_dependencies_ids')):
            for providing_project_dependencies_id in filtered_project.get('providing_project_dependencies_ids'):
                dependent_project = [project_dependency for project_dependency in project_dependencies if project_dependency.get('id') == providing_project_dependencies_id]
                if any(dependent_project):
                    # Get dependent project record to get dependency info (we're only interested in dependencies that match the filter criteria)
                    project_dependent_record = filter_projects([project for project in projects if project.get('id') == dependent_project[0].get('dependent_project_id')],
                                                                product_filter, 
                                                                category_filter)
                    if any(project_dependent_record):
                        final_data_record["used_by"].append({
                            "id": project_dependent_record[0].get('id'),
                            "permalink": project_dependent_record[0].get('permalink'),
                            "owner": project_dependent_record[0].get('project_stakeholder_owner_name'),
                            "weighting": len(project_dependent_record[0].get('dependent_project_dependencies_ids'))
                        })

        final_data_set.append(final_data_record)

    if len(final_data_set) > 0:
        # Sort data set by weighting
        final_data_set = sorted(final_data_set, key=lambda x: x['weighting'])        

        # Filter projects by project_filter
        filtered_projects = [prj for prj in final_data_set if prj['permalink'] == project_filter]

        if len(filtered_projects) > 0:        
            # Write all project dependency data filtered by product and category to JSON file depending on export_all_data flag
            if export_all_data == 'Y':
                save_to_json(f'./data/{product_filter}/project-dependency.json', final_data_set)

            # Write project dependency data filtered by product, category & project to JSON file
            save_to_json(f'./data/{project_filter}/project-dependency.json', filtered_projects)
                
            # Initialize and configure Graphviz directed graph
            dot = graphviz.Digraph(name='Component Dependency Graph', strict=True, format='pdf', graph_attr={'rankdir':'LR'}, 
                                   node_attr={'shape':'rectangle','arrowhead':'normal','arrowsize':'0.5','fontname':'Arial','fontsize':'11','style':'filled','color':'lightblue'})

            # Keep track of nodes/edges to avoid duplicates
            added_nodes = set()
            added_edges = set()

            # Do the thing I was created to do! [0_o]
            build_dependency_graph(dot, added_nodes, added_edges, project_list=final_data_set, source_project_nodes=filtered_projects, graph_type=graph_type,
                                max_depth=max_depth, depth=0)

            # Generate and save the graph to ./renders folder
            output_file = f'./renders/{project_filter}-{graph_type}-dependency-graph'
            dot.render(filename=output_file, view=True)
            print(f"Dependency graph saved to {output_file}.pdf")
        else:
            print("No projects found that match project filter.")
    else:
        print("No projects found that match product or category criteria.")
        
# You can only choose the path I've laid for you...mwahahaha!
def validate_graph_type(graph_type):
    if graph_type not in ['uses', 'usedby']:
        raise argparse.ArgumentTypeError(f"Invalid graph type: {graph_type}. Please enter either 'uses' or 'usedby'.")
    return graph_type

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a dependency graph of Projects")

    parser.add_argument('--product_filter', required=True, type=str, help='Filter projects by Product(s). Example: Foundation')
    parser.add_argument('--category_filter', required=True, type=str, help='Filter projects by Categories(s). Example: Infrastructure,Service')
    parser.add_argument('--project_filter', required=True, type=str, help='Determines which project you want to build the dependency graph for. Filters on project permalink. Example: sfn-kubernetes')
    parser.add_argument('--graph_type', required=True, type=validate_graph_type, help='Determines the type of dependency to graph to build. Expected values are: uses or usedby')
    parser.add_argument('--export_all_data', type=str, help='Determines if all data (filtered by product and category) is to be exported to JSON. Default is N')
    parser.add_argument('--max_depth', type=int, help='Determines the maximum depth to build dependencies for a given project. Defaults to 2')

    args = parser.parse_args()

    # Pass the arguments to the main function
    main(args)