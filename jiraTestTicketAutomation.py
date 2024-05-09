import requests
import subprocess
from requests.auth import HTTPBasicAuth
import pandas as pd
import json,os
import argparse

account_id=""
routing_id =""
org_id = ""
project_id = ""
pipeline_id = ""

def map_to_project_key(team, mapping_csv_path):
    mapping_df = pd.read_csv(mapping_csv_path)
    project_key = mapping_df[mapping_df['Team'] == team]['Project_key'].values
    return project_key[0] if len(project_key) > 0 else "CDS"

def find_team_owned_by(class_name, output_csv_path):
    # Load the CSV file
    df = pd.read_csv(output_csv_path)

    # Group by 'Module' and 'OwnedBy', and count the occurrences
    grouped = df.groupby(['Module', 'OwnedBy']).size().reset_index(name='Count')

    # Sort the results to ensure the ordering is correct for max selection
    grouped.sort_values(by=['Module', 'Count'], ascending=[True, False], inplace=True)

    final_results = pd.DataFrame()

    # Iterate over each unique module
    for module in df['Module'].unique():
        module_group = grouped[grouped['Module'] == module]

        if module_group.empty:
            continue

        top_result = module_group.iloc[0]
        if top_result['OwnedBy'].lower() == 'unknown' and len(module_group) > 1:
            # If the top is 'unknown' and there are other entries, take the next best
            next_best = module_group.iloc[1]
            final_results = pd.concat([final_results, next_best.to_frame().T], ignore_index=True)
        else:
            # If the top is not 'unknown' or it's the only entry
            final_results = pd.concat([final_results, top_result.to_frame().T], ignore_index=True)

    # Add a column to explicitly mark modules with only 'unknown' values if needed
    final_results['Note'] = final_results.apply(lambda row: 'Only unknown values' if row['OwnedBy'].lower() == 'unknown' else '', axis=1)

    # Find the entry for the given class name in the original DataFrame
    output_entry = df[df['ClassName'] == class_name]

    if not output_entry.empty and output_entry.iloc[0]['OwnedBy'].lower() != "unknown":
        # If the class name is found and the OwnedBy is not 'Unknown'
        return output_entry.iloc[0]['OwnedBy']
    else:
        # If OwnedBy is 'Unknown' or class name not found, look up the corresponding module in the processed DataFrame
        if not output_entry.empty:
            module = output_entry.iloc[0]['Module']
            normalized_entry = final_results[final_results['Module'] == module3]
            
            if not normalized_entry.empty:
                return normalized_entry.iloc[0]['OwnedBy']
    
    return "Not Found"


def fetch_team_owner_email(token, project_key):
    # Define the curl command to fetch the file
    curl_command = [
        "curl", "-H", f"Authorization: token {token}",
        "-H", "Accept: application/vnd.github.v3.raw",
        "https://api.github.com/repos/wings-software/engops-utilities/contents/data/jira-data.yaml"
    ]

    # Define the awk command to parse the file and extract the first owner's email for the given project key
    awk_command = [
        "awk", f"/^{project_key}:/{{f=1;next}} /^[A-Z]+:/{{f=0}} f && /owners:/{{getline; print $2; exit}}"
    ]

    # Execute the curl command
    curl_process = subprocess.Popen(curl_command, stdout=subprocess.PIPE)
    # Pipe the output of curl to awk to process it
    awk_process = subprocess.Popen(awk_command, stdin=curl_process.stdout, stdout=subprocess.PIPE, text=True)
    curl_process.stdout.close()  # Allow curl_process to receive a SIGPIPE if awk_process exits.

    # Get the output from awk
    output, _ = awk_process.communicate()

    if output:
        return(output.strip())
    else:
        print(f"No details found for project key '{project_key}'.")

def create_ticket(gh_token, classname,testcase_name,user_email,jira_token,test_type):
    team = find_team_owned_by(classname,'./output.csv')
    team_project_key = map_to_project_key(team,'./mapping.csv')
    owner_email = fetch_team_owner_email(gh_token,team_project_key)
    owner_jira = search_jira_user(owner_email,user_email,jira_token)
    url = "https://harness.atlassian.net/rest/api/3/issue"
    test = ""
    if (test_type=="UT"): 
        test = "Unit Test"
    else :
        test = "Integration Test"
    auth = HTTPBasicAuth(f"{user_email}", f"{jira_token}")

    headers = {
    "Accept": "application/json",
    "Content-Type": "application/json"
    }

    payload = json.dumps({
        "fields": {
            "assignee" : {
                "accountId" : f"{owner_jira}"
            },
            "reporter" : {
                "accountId" : f"{owner_jira}"
            },
            "labels" : [
                f"{classname}" ,
                f"{testcase_name}"
            ],
            "components" : [
                { "name" : "two"}
            ],
            "project" : 
                { "key" : f"TJI"},
            "issuetype" : 
                { "name" : "Bug"},
            "summary" : f"{test} : \"{testcase_name}\" failed in Test Class : \"{classname}\"",
            "description": 
            {
                "version": 1,
                "type": "doc",
                "content": [
                    {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": f"{test} : \"{testcase_name}\" has failed in the test class : \"{classname}\". Please triage and fix the same."
                        }
                    ]
                    },
                    {
                    "type" : "paragraph",
                    "content" : [
                        {
                            "type" : "text",
                            "text" : f"If you are not the rightful owner, please review and assign the right owner through the @OwnedBy annotation for the test class : \"{classname}\"",
                            "marks": [
                                {
                                    "type": "em"
                                },
                                {
                                    "type": "strong"
                                }
                            ]
                        }
                    ]
                    }
                ]
        }
        }
    })

    response = requests.request(
    "POST",
    url,
    data=payload,
    headers=headers,
    auth=auth
    )

    print(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": ")))

def fetch_test_cases(build_id, auth_token):
    # Updated base URL and parameters as per the curl command
    base_url = "https://app.harness.io/gateway/ti-service/reports/test_cases"
    params = {
        "routingId": f"{routing_id}",
        "accountId": f"{account_id}",
        "orgId": f"{org_id}",
        "projectId": f"{project_id}",
        "buildId": f"{build_id}",  # Use the build_id argument
        "pipelineId": f"{pipeline_id}",
        "report": "junit",
        "status": "failed",
        "testCaseSearchTerm": "",
        "sort": "status",
        "order": "ASC",
        "pageIndex": 0,
        "pageSize": 10,
    }
    # Updated headers with the new auth_token
    headers = {"Authorization": f"Bearer {auth_token}"}
    
    response = requests.get(base_url, headers=headers, params=params)
    if response.status_code == 200:
        return response.json()["content"]
    else:
        print(f"Failed to fetch data from URL. Status code: {response.status_code}")
        return []

def search_jira(email, api_token,test_case_name,class_name):
    url = "https://harness.atlassian.net/rest/api/3/search"
    jql = f"project = TJI AND component=\"two\" AND labels=\"{test_case_name}\" AND labels=\"{class_name}\" AND statusCategory NOT IN (Done)"
    auth = (email, api_token)
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    data = {"jql": jql, "maxResults": 100, "startAt": 0}
    response = requests.post(url, auth=auth, headers=headers, json=data)
    if response.status_code == 200:
        issues = response.json().get("issues", [])
        ticket_ids = [issue["key"] for issue in issues]
        return ticket_ids
    else:
        print(f"Failed to search Jira. Status code: {response.status_code}")
        return []

def search_jira_user(pr_email, user_email, api_token):
    """
    Search for a Jira user by email address.

    :param email: The email address associated with the Jira account making the request.
    :param user_email: The email address of the user to search for in Jira.
    :param api_token: The API token for authentication.
    :return: A list of users that match the search query or an empty list if the request fails.
    """
    url = f"https://harness.atlassian.net/rest/api/3/user/search?query={pr_email}"
    auth = (user_email, api_token)
    headers = {"Accept": "application/json"}

    response = requests.get(url, auth=auth, headers=headers)

    if response.status_code == 200:
        return response.json()[0]["accountId"]  # Returns a list of user objects that match the search query
    else:
        print(f"Failed to search for Jira user. Status code: {response.status_code}")
        return []

def add_watcher(pr_email,ticket_ids,email,api_token):
    issue_key = ticket_ids[0]
    pr_owner_jira_id = search_jira_user(pr_email,email,api_token)
    url = f"https://harness.atlassian.net/rest/api/3/issue/{issue_key}/watchers"
    auth = (email, api_token)
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    data = f'"{pr_owner_jira_id}"'  # The accountId should be sent as a JSON string

    response = requests.post(url, auth=auth, headers=headers, data=data)

    if response.status_code in [200, 204]:
        print(f"Watcher added successfully to issue {issue_key}.")
    else:
        print(f"Failed to add watcher to issue. Status code: {response.status_code}, Response: {response.text}")

    return response.status_code, response.text

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Jira Ticket Automation')
    parser.add_argument('--gh_token', help='GitHub access token', required=True)
    parser.add_argument('--build_id', help='Build Id of the pipeline', required=True)
    parser.add_argument('--auth_token_ti', help='Authentication token for fetching the test cases from TI for the pipeline', required=True)
    parser.add_argument('--account_id', help='Account ID of the pipeline', required=True)
    parser.add_argument('--org_id', help='Organisation ID of the pipeline', required=True)
    parser.add_argument('--project_id', help='Project ID of the pipeline', required=True)
    parser.add_argument('--pipeline_id', help='ID of the pipeline', required=True)

    args = parser.parse_args()
    pr_value = os.getenv('PR')
    account_id = args.account_id
    routing_id = account_id
    org_id = args.org_id
    project_id = args.project_id
    pipeline_id = args.pipeline_id

    # Parameters for fetching test cases
    # build_id = "2"
    # auth_token_ti = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJhdXRoVG9rZW4iOiI2NWY3ZWY4ZGZhNzk0ODI5OTI2YzVjZjEiLCJpc3MiOiJIYXJuZXNzIEluYyIsImV4cCI6MTcxMTEwNTc4MCwiZW52IjoiZ2F0ZXdheSIsImlhdCI6MTcxMTAxOTMyMH0.Xo9o5mH7QCppPEsGT2bj4VQLeokqEoOKotnuf-kgXDc"
    # Parameters for Jira search
    email = "routhu.shashank@harness.io"
    jira_api_token = "ATATT3xFfGF0Jo759u2-PsRRvool8QlI8HomslDfN0JkBWWmc7YL4bSGUB6sbSfth5Px0knllOb1L1I92tFA6xg8JahO1jbDAbxPg7WXCBWcdVxMB-xIPgEHlkeyYtMXhOts4MpoCH00fiSlxhK4xQhy--3gJ3z7Ezn0aq_fmR4A185S5bb2okQ=296F6AE4"
    pr_email = "pankaj.kumar@harness.io"
    # Fetch test cases
    test_cases = fetch_test_cases(args.build_id, args.auth_token_ti)
    test_type = os.getenv('test_type')
    # gh_token = "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"
    
    # Assuming you do something here with test_cases, like mapping them with a CSV file

    for test_case in test_cases:
        test_case_name = test_case["name"]
        class_name = test_case["class_name"]
        ticket_ids = search_jira(email, jira_api_token,test_case_name, class_name)
        if ticket_ids:
            add_watcher(pr_email,ticket_ids,email,jira_api_token)
            print("Found Jira Ticket ID(s):")
            for ticket_id in ticket_ids:
                print(ticket_id)
        else:
            create_ticket(args.gh_token,class_name,test_case_name,email,jira_api_token,test_type)
            print(f"{test_case_name} , {class_name}")


