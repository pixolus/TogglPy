"""
TogglPy is a non-cluttered, easily understood and implemented
library for interacting with the Toggl API.

Copyright (c) 2018-2023 Matthew Downey
Copyright (c) 2024 Marco Lierfeld, pixolus GmbH
"""
import json  # parsing json data
import math
import sys
import time
from base64 import b64encode
from datetime import datetime
from typing import Optional, Dict, List, Union

# for making requests
cafile = None
from urllib.parse import urlencode
from urllib.request import Request, urlopen
try:
    import certifi
    cafile = certifi.where()
except ImportError:
    pass


NumStr = Union[str, int]
TogglResponseDict = Dict[str, Union[Dict, List, str, bool, type(None)]] # JSON with string keys
TogglResponse = Optional[TogglResponseDict] # JSON if currently logging, None otherwise
TogglResponses = Optional[List[TogglResponseDict]] # List of JSON dicts

# --------------------------------------------
# Class containing the endpoint URLs for Toggl
# --------------------------------------------
class Endpoints:
    # REPORT_WEEKLY = "https://api.track.toggl.com/reports/api/v2/weekly"
    # REPORT_DETAILED = "https://api.track.toggl.com/reports/api/v2/details"
    # REPORT_SUMMARY = "https://api.track.toggl.com/reports/api/v2/summary"
    TIME_ENTRIES = "https://api.track.toggl.com/api/v9/workspaces/{}/time_entries"
    TIME_ENTRY = "https://api.track.toggl.com/api/v9/workspaces/{}/time_entries/{}"
    CURRENT = "https://api.track.toggl.com/api/v9/me/time_entries/current"
    START = "https://api.track.toggl.com/api/v9/workspaces/{}/time_entries"
    STOP = "https://api.track.toggl.com/api/v9/workspaces/{}/time_entries/{}/stop"
    CLIENTS = "https://api.track.toggl.com/api/v9/me/clients"
    PROJECTS = "https://api.track.toggl.com/api/v9/me/projects"
    WORKSPACES = "https://api.track.toggl.com/api/v9/me/workspaces"
    WORKSPACE_PROJECTS = "https://api.track.toggl.com/api/v9/workspaces/{0}/projects"
    WORKSPACE_CLIENTS = "https://api.track.toggl.com/api/v9/workspaces/{0}/clients"
    PROJECT_TASKS = "https://api.track.toggl.com/api/v9/workspaces/{0}/projects/{1}/tasks"
    TASKS = "https://api.track.toggl.com/api/v9/workspaces/{0}/projects/{1}/tasks"
    CURRENT_RUNNING_TIME = "https://api.track.toggl.com/api/v9/me/time_entries/current"


# ------------------------------------------------------
# Class containing the necessities for Toggl interaction
# ------------------------------------------------------
class Toggl:
    # template of headers for our request
    headers = {
        "Authorization": "",
        "Content-Type": "application/json",
        "Accept": "*/*",
        "User-Agent": "python/urllib",
    }

    # default API user agent value
    user_agent = "TogglPy"

    # ------------------------------------------------------------
    # Auxiliary methods
    # ------------------------------------------------------------

    def decodeJSON(self, json_string: str) -> Union[TogglResponse, TogglResponses]:
        decoded = json.JSONDecoder().decode(json_string)
        # ugly workaround: The toggl API returns a JSON object which cannot be
        # sent back to the API, because the `tag_ids` are `null` which is not allowed on a POST/PUT/PATCH
        if 'tag_ids' in decoded and decoded.get('tag_ids') is None:
            decoded['tag_ids'] = []
        return decoded

    # ------------------------------------------------------------
    # Methods that modify the headers to control our HTTP requests
    # ------------------------------------------------------------
    def setAPIKey(self, api_key: str):
        """set the API key in the request header"""
        # craft the Authorization
        authHeader = api_key + ":" + "api_token"
        authHeader = "Basic " + b64encode(authHeader.encode()).decode('ascii').rstrip()

        # add it into the header
        self.headers['Authorization'] = authHeader

    def setAuthCredentials(self, email: str, password: str):
        auth_header = '{0}:{1}'.format(email, password)
        auth_header = "Basic " + b64encode(auth_header.encode()).decode('ascii').rstrip()

        # add it into the header
        self.headers['Authorization'] = auth_header

    def setUserAgent(self, agent: str):
        """set the User-Agent setting, by default it's set to TogglPy"""
        self.user_agent = agent

    # -----------------------------------------------------
    # Methods for directly requesting data from an endpoint
    # -----------------------------------------------------

    def requestRaw(self, endpoint: str, parameters=None) -> str:
        """make a request to the toggle api at a certain endpoint and return the RAW page data (usually JSON)"""
        if parameters is None:
            return urlopen(Request(endpoint, headers=self.headers), cafile=cafile).read()
        else:
            if 'user_agent' not in parameters:
                parameters.update({'user_agent': self.user_agent})  # add our class-level user agent in there
            # encode all of our data for a get request & modify the URL
            endpoint = endpoint + "?" + urlencode(parameters)
            # make request and read the response
            return urlopen(Request(endpoint, headers=self.headers), cafile=cafile).read()

    def request(self, endpoint: str, parameters=None) -> Union[TogglResponse, TogglResponses]:
        """make a request to the toggle api at a certain endpoint and return the page data as a parsed JSON dict"""
        return self.decodeJSON(self.requestRaw(endpoint, parameters).decode(encoding='utf-8'))

    def postRequest(self, endpoint: str, parameters=None, method: str='POST') -> str:
        """make a POST request to the toggle api at a certain endpoint and return the RAW page data (usually JSON)"""
        if method == 'DELETE':  # Calls to the API using the DELETE method return an HTTP response rather than JSON
            return urlopen(Request(endpoint, headers=self.headers, method=method), cafile=cafile).code
        if parameters is None:
            return urlopen(
                Request(endpoint, headers=self.headers, method=method), cafile=cafile
            ).read().decode('utf-8')
        else:
            data = json.JSONEncoder().encode(parameters)
            binary_data = data.encode('utf-8')
            # make request and read the response
            return urlopen(
                Request(endpoint, data=binary_data, headers=self.headers, method=method), cafile=cafile
            ).read().decode(encoding='utf-8')

    # ---------------------------------
    # Methods for managing Time Entries
    # ---------------------------------

    def startTimeEntry(self, description: NumStr, wid: NumStr, pid: NumStr=None, tag: Optional[str]=None) -> TogglResponse:
        """starts a new Time Entry"""
        
        import time
        from datetime import datetime
        now = time.time()
        start_rfc3339 = datetime.utcfromtimestamp(now).isoformat(timespec="seconds") + "Z"
        
        tags = []
        if tag: tags.append(tag)

        json_dict = {
            "tags": tags,
            "start": start_rfc3339,
            "duration": -1 * int(now),
            "workspace_id": int(wid),
            "project_id": int(pid),
            "description": description,
            "created_with": self.user_agent
        }
        
        state = self.postRequest(Endpoints.START.format(wid), parameters=json_dict)
        return self.decodeJSON(state)

    def currentRunningTimeEntry(self, state: TogglResponse=None) -> TogglResponse:
        """Gets the Current Time Entry"""
        if state is None:
            state = self.request(Endpoints.CURRENT_RUNNING_TIME)
        return state

    def stopTimeEntry(self, state: TogglResponse=None) -> TogglResponse:
        """Stop the time entry"""
        state = self.currentRunningTimeEntry(state)
        if state is None: return None
        
        state = self.postRequest(Endpoints.STOP.format(state['workspace_id'], state['id']), method="PATCH")
        return self.decodeJSON(state)

    def createTimeEntry(self, hour_duration: int, wid: int, description: str=None, project_id: int=None,
            projectname: str=None, taskid: int=None, client_name: str=None, year: int=None, month: int=None,
            day: int=None, hour: int=None, billable: bool=False, hour_diff: int=-2) -> TogglResponse:
        """
        Creating a custom time entry, minimum must is hour duration and project param
        :param hour_duration: Duration of the time entry in hours.
        :param wid The id of the time entry's workspace
        :param description: Sets a description for the newly created time entry
        :param project_id: Not required if projectname given
        :param projectname: Not required if project_id was given
        :param taskid: Adds a task to the time entry (Requirement: Toggl Starter or higher)
        :param client_name: Can speed up project query process
        :param year: Taken from now() if not provided
        :param month: Taken from now() if not provided
        :param day: Taken from now() if not provided
        :param hour: Taken from now() if not provided
        :param billable: True if the time entry is billable
        :param hour_diff: Time difference in hours added to the `hours` parameter
        :return: response object from post call
        """

        if not project_id:
            if projectname and client_name:
                project_id = (self.getClientProject(client_name, projectname))['data']['id']
            elif projectname:
                project_id = (self.searchClientProject(projectname))['data']['id']
            else:
                print('Too many missing parameters for query')
                exit(1)

        year = datetime.now().year if not year else year
        month = datetime.now().month if not month else month
        day = datetime.now().day if not day else day
        hour = datetime.now().hour if not hour else hour

        timestruct = datetime(year, month, day, hour + hour_diff).isoformat() + '.000Z'
        time_entry = {
            'start': timestruct,
            'duration': hour_duration * 3600,
            'pid': project_id,
            'created_with': 'NAME',
            'billable': billable
        }

        if description:
            time_entry['description'] = description

        if taskid:
            time_entry['tid'] = taskid

        response = self.postRequest(Endpoints.TIME_ENTRIES.format(wid), parameters=time_entry)
        return self.decodeJSON(response)

    def putTimeEntry(self, parameters: TogglResponse) -> TogglResponse:
        if 'id' not in parameters:
            raise Exception("An id must be provided in order to put a time entry")
        id = parameters['id']
        if type(id) is not int:
            raise Exception("Invalid id %s provided " % id)
        if 'workspace_id' not in parameters:
            raise Exception("A workspace_id must be provided in order to put a time entry")
        wid = parameters['workspace_id']
        if type(wid) is not int:
            raise Exception("Invalid workspace_id %s provided " % wid)
        endpoint = Endpoints.TIME_ENTRY.format(wid, id)  # encode all of our data for a put request & modify the URL
        response = self.postRequest(endpoint, parameters=parameters, method='PUT')
        
        return self.decodeJSON(response)

    def deleteTimeEntry(self, workspace_id: int, entry_id: int) -> str:
        """Delete the time entry"""
        endpoint = Endpoints.TIME_ENTRY.format(workspace_id, entry_id)
        response = self.postRequest(endpoint, method='DELETE')
        return response

    # ----------------------------------
    # Methods for getting workspace data
    # ----------------------------------
    def getWorkspaces(self) -> TogglResponses:
        """return all the workspaces for a user"""
        return self.request(Endpoints.WORKSPACES)

    def getWorkspace(self, name=None, workspace_id=None) -> TogglResponse:
        """return the first workspace that matches a given name or id"""
        workspaces = self.getWorkspaces()  # get all workspaces

        # if they give us nothing let them know we're not returning anything
        if name is None and workspace_id is None:
            print("Error in getWorkspace(), please enter either a name or an id as a filter")
            return None

        if workspace_id is None:  # then we search by name
            for workspace in workspaces:  # search through them for one matching the name provided
                if workspace['name'] == name:
                    return workspace  # if we find it return it
        else:  # otherwise search by id
            for workspace in workspaces:  # search through them for one matching the id provided
                if workspace['id'] == int(workspace_id):
                    return workspace  # if we find it return it
        return None  # if we get to here and haven't found it return None

    def getWorkspaceProjects(self, workspace_id: int) -> TogglResponses:
        """
        Return all projects for a given Workspace.
        
        :param workspace_id: Workspace ID by which to query
        :return: Projects object returned from endpoint
        """

        return self.request(Endpoints.WORKSPACE_PROJECTS.format(workspace_id))

    # -------------------------------
    # Methods for getting client data
    # -------------------------------

    def getClients(self) -> TogglResponses:
        """return all clients that are visible to a user"""
        return self.request(Endpoints.CLIENTS)

    def getClient(self, name: str=None, client_id: int=None) -> TogglResponse:
        """return the first workspace that matches a given name or id"""
        clients = self.getClients()  # get all clients

        # if they give us nothing let them know we're not returning anything
        if name is None and client_id is None:
            print("Error in getClient(), please enter either a name or an id as a filter")
            return None

        if client_id is None:  # then we search by name
            for client in clients:  # search through them for one matching the name provided
                if client['name'] == name:
                    return client  # if we find it return it
            return None  # if we get to here and haven't found it return None
        else:  # otherwise search by id
            for client in clients:  # search through them for one matching the id provided
                if client['id'] == int(client_id):
                    return client  # if we find it return it
            return None  # if we get to here and haven't found it return None

    # def getClientProjects(self, id, active='true'):
    #     """
    #     :param id: Client ID by which to query
    #     :param active: possible values true/false/both. By default true. If false, only archived projects are returned.
    #     :return: Projects object returned from endpoint
    #     """
    #     return self.request(Endpoints.CLIENTS + '/{0}/projects?active={1}'.format(id, active))

    # def searchClientProject(self, name) -> TogglResponse:
    #     """
    #     Provide only a projects name for query and search through entire available names
    #     WARNING: Takes a long time!
    #              If client name is known, 'getClientProject' would be advised
    #     :param name: Desired Project's name
    #     :return: Project object
    #     """
    #     for client in self.getClients():
    #         try:
    #             for project in self.getClientProjects(client['id']):
    #                 if project['name'] == name:
    #                     return project
    #         except Exception:
    #             continue
    #
    #     print('Could not find client by the name')
    #     return None

    # def getClientProject(self, clientName, projectName):
    #     """
    #     Fast query given the Client's name and Project's name
    #     :param clientName:
    #     :param projectName:
    #     :return:
    #     """
    #     for client in self.getClients():
    #         if client['name'] == clientName:
    #             cid = client['id']
    #
    #     if not cid:
    #         print('Could not find such client name')
    #         return None
    #
    #     for projct in self.getClientProjects(cid):
    #         if projct['name'] == projectName:
    #             pid = projct['id']
    #
    #     if not pid:
    #         print('Could not find such project name')
    #         return None
    #
    #     return self.getProject(pid)

    # --------------------------------
    # Methods for getting PROJECTS data
    # --------------------------------
    def getProjects(self) -> TogglResponses:
        """return all projects that are visible to a user"""
        return self.request(Endpoints.PROJECTS)
    
    def getProject(self, wid: NumStr, pid: NumStr) -> TogglResponse:
        """return project data"""
        return self.request(Endpoints.WORKSPACE_PROJECTS.format(wid) + '/{0}'.format(pid))

    def getProjectTasks(self, wid: NumStr, pid: NumStr) -> TogglResponses:
        """
        return all tasks of a given project
        :param wid: Workspace ID
        :param pid: Project ID
        """
        return self.request(Endpoints.PROJECT_TASKS.format(wid, pid))

    # --------------------------------
    # Methods for interacting with TASKS data
    # --------------------------------

    def createTask(self, name: str, wid: NumStr, pid: NumStr, active: bool=True, estimated_seconds: bool=False) -> TogglResponse:
        """
        create a new task (Requirement: Toggl Starter or higher)
        :param name: Name of the task
        :param wid: Workspace ID
        :param pid: Project ID
        :param active: Defines if the task is active or archived, default: active
        :param estimated_seconds: Estimation for the task in seconds
        """

        data = {
            'name': name,
            'workspace_id': int(wid),
            'project_id': int(pid),
            'active': active,
            'estimated_seconds': estimated_seconds
        }

        response = self.postRequest(Endpoints.TASKS.format(wid, pid), parameters=data)
        return self.decodeJSON(response)

    # --------------------------------
    # Methods for getting reports data
    # ---------------------------------
    # def getWeeklyReport(self, data):
    #     """return a weekly report for a user"""
    #     return self.request(Endpoints.REPORT_WEEKLY, parameters=data)
    #
    # def getWeeklyReportPDF(self, data, filename):
    #     """save a weekly report as a PDF"""
    #     # get the raw pdf file data
    #     filedata = self.requestRaw(Endpoints.REPORT_WEEKLY + ".pdf", parameters=data)
    #
    #     # write the data to a file
    #     with open(filename, "wb") as pdf:
    #         pdf.write(filedata)
    #
    # def getDetailedReport(self, data):
    #     """return a detailed report for a user"""
    #     return self.request(Endpoints.REPORT_DETAILED, parameters=data)
    #
    # def getDetailedReportPages(self, data):
    #     """return detailed report data from all pages for a user"""
    #     pages_index = 1
    #     data['page'] = pages_index
    #     pages = self.request(Endpoints.REPORT_DETAILED, parameters=data)
    #     try:
    #         pages_number = math.ceil(pages.get('total_count', 0) / pages.get('per_page', 0))
    #     except ZeroDivisionError:
    #         pages_number = 0
    #     for pages_index in range(2, pages_number + 1):
    #         time.sleep(1)  # There is rate limiting of 1 request per second (per IP per API token).
    #         data['page'] = pages_index
    #         pages['data'].extend(self.request(Endpoints.REPORT_DETAILED, parameters=data).get('data', []))
    #     return pages
    #
    # def getDetailedReportPDF(self, data, filename):
    #     """save a detailed report as a pdf"""
    #     # get the raw pdf file data
    #     filedata = self.requestRaw(Endpoints.REPORT_DETAILED + ".pdf", parameters=data)
    #
    #     # write the data to a file
    #     with open(filename, "wb") as pdf:
    #         pdf.write(filedata)
    #
    # def getDetailedReportCSV(self, data, filename=None):
    #     """save a detailed report as a csv"""
    #     # get the raw pdf file data
    #     filedata = self.requestRaw(Endpoints.REPORT_DETAILED + ".csv", parameters=data)
    #
    #     if filename:
    #         # write the data to a file
    #         with open(filename, "wb") as pdf:
    #             pdf.write(filedata)
    #     else:
    #         return filedata
    #
    # def getSummaryReport(self, data):
    #     """return a summary report for a user"""
    #     return self.request(Endpoints.REPORT_SUMMARY, parameters=data)
    #
    # def getSummaryReportPDF(self, data, filename):
    #     """save a summary report as a pdf"""
    #     # get the raw pdf file data
    #     filedata = self.requestRaw(Endpoints.REPORT_SUMMARY + ".pdf", parameters=data)
    #
    #     # write the data to a file
    #     with open(filename, "wb") as pdf:
    #         pdf.write(filedata)

    # --------------------------------
    # Methods for creating, updating, and deleting clients
    # ---------------------------------
    def createClient(self, name: str, wid: int, notes: str=None) -> TogglResponse:
        """
        create a new client
        :param name: Name the client
        :param wid: Workspace ID
        :param notes: Notes for the client (optional)
        """

        data = {
            'name': name,
            'wid': wid,
            'notes': notes
        }
        
        response = self.postRequest(Endpoints.WORKSPACE_CLIENTS.format(wid), parameters=data)
        return self.decodeJSON(response)

    def updateClient(self, wid: int, id: int, name: str=None, notes: str=None) -> TogglResponse:
        """
        Update data for an existing client. If the name or notes parameter is not
        supplied, the existing data on the Toggl server will not be changed.
        :param wid: The id of the client's workspace
        :param id: The id of the client to update
        :param name: Update the name of the client (optional)
        :param notes: Update the notes for the client (optional)
        """

        data = {
            'name': name,
            'notes': notes,
            'wid:': wid
        }

        response = self.postRequest(
                Endpoints.WORKSPACE_CLIENTS.format(wid) + '/{0}'.format(id),
                parameters=data,
                method='PUT'
        )
        return self.decodeJSON(response)

    def deleteClient(self, wid: int, id: int) -> str:
        """
        Delete the specified client
        :param wid: The id of the client's workspace
        :param id: The id of the client to delete
        """
        response = self.postRequest(Endpoints.WORKSPACE_CLIENTS.format(wid) + '/{0}'.format(id), method='DELETE')
        return response
