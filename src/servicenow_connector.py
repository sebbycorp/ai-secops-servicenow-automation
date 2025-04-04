#!/usr/bin/env python3
# ServiceNow Connector for AI-Assisted SecOps Workflow

import os
import requests
import json
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('servicenow_connector')

class ServiceNowConnector:
    """
    Handles communication with ServiceNow API for the AI-Assisted SecOps workflow.
    """
    
    def __init__(self, instance_url, username=None, password=None, oauth_token=None):
        """
        Initialize ServiceNow connector with authentication details.
        
        Args:
            instance_url (str): ServiceNow instance URL
            username (str, optional): Basic auth username
            password (str, optional): Basic auth password
            oauth_token (str, optional): OAuth token for authentication
        """
        self.instance_url = instance_url
        self.base_api_url = f"https://{instance_url}/api/now"
        
        # Set up authentication
        self.auth = None
        self.headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        
        if oauth_token:
            self.headers['Authorization'] = f"Bearer {oauth_token}"
        elif username and password:
            self.auth = (username, password)
        else:
            raise ValueError("Either (username, password) or oauth_token must be provided")
    
    def get_my_tickets(self, assignment_group="SecOps", status=None):
        """
        Get tickets assigned to the current user's group.
        
        Args:
            assignment_group (str): Assignment group to filter by
            status (str, optional): Ticket status to filter by
            
        Returns:
            list: List of ticket objects
        """
        endpoint = f"{self.base_api_url}/table/change_request"
        
        # Build query parameters
        query_params = {
            'sysparm_query': f'assignment_group.name={assignment_group}',
            'sysparm_display_value': 'true',
            'sysparm_fields': 'number,short_description,description,state,approval,assignment_group',
            'sysparm_limit': '10'
        }
        
        if status:
            query_params['sysparm_query'] += f'^state={status}'
        
        try:
            response = requests.get(
                endpoint,
                auth=self.auth,
                headers=self.headers,
                params=query_params
            )
            response.raise_for_status()
            
            tickets = response.json().get('result', [])
            logger.info(f"Retrieved {len(tickets)} tickets from ServiceNow")
            return tickets
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error retrieving tickets: {str(e)}")
            return []
    
    def get_ticket_details(self, ticket_number):
        """
        Get detailed information about a specific ticket.
        
        Args:
            ticket_number (str): The ticket number to retrieve
            
        Returns:
            dict: Ticket details or None if not found
        """
        endpoint = f"{self.base_api_url}/table/change_request"
        
        query_params = {
            'sysparm_query': f'number={ticket_number}',
            'sysparm_display_value': 'true',
            'sysparm_limit': '1'
        }
        
        try:
            response = requests.get(
                endpoint,
                auth=self.auth,
                headers=self.headers,
                params=query_params
            )
            response.raise_for_status()
            
            results = response.json().get('result', [])
            if results:
                ticket = results[0]
                
                # Get associated tasks
                tasks = self.get_associated_tasks(ticket['sys_id'])
                ticket['tasks'] = tasks
                
                return ticket
            else:
                logger.warning(f"Ticket {ticket_number} not found")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error retrieving ticket details: {str(e)}")
            return None
    
    def get_associated_tasks(self, change_sys_id):
        """
        Get tasks associated with a change request.
        
        Args:
            change_sys_id (str): System ID of the change request
            
        Returns:
            list: List of task objects
        """
        endpoint = f"{self.base_api_url}/table/change_task"
        
        query_params = {
            'sysparm_query': f'change_request={change_sys_id}',
            'sysparm_display_value': 'true',
            'sysparm_fields': 'number,short_description,description,state,assigned_to,assignment_group',
        }
        
        try:
            response = requests.get(
                endpoint,
                auth=self.auth,
                headers=self.headers,
                params=query_params
            )
            response.raise_for_status()
            
            tasks = response.json().get('result', [])
            logger.info(f"Retrieved {len(tasks)} tasks for change {change_sys_id}")
            return tasks
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error retrieving tasks: {str(e)}")
            return []
    
    def update_ticket_approval(self, ticket_number, approval_status, approver_name, comment=None):
        """
        Update the approval status of a ticket.
        
        Args:
            ticket_number (str): The ticket number to update
            approval_status (str): New approval status ('approved', 'rejected', etc.)
            approver_name (str): Name of the approver
            comment (str, optional): Approval comment
            
        Returns:
            bool: Success status
        """
        # First, get the sys_id for the ticket
        endpoint = f"{self.base_api_url}/table/change_request"
        
        query_params = {
            'sysparm_query': f'number={ticket_number}',
            'sysparm_fields': 'sys_id',
            'sysparm_limit': '1'
        }
        
        try:
            response = requests.get(
                endpoint,
                auth=self.auth,
                headers=self.headers,
                params=query_params
            )
            response.raise_for_status()
            
            results = response.json().get('result', [])
            if not results:
                logger.warning(f"Ticket {ticket_number} not found for approval update")
                return False
                
            sys_id = results[0]['sys_id']
            
            # Now update the approval
            update_endpoint = f"{self.base_api_url}/table/change_request/{sys_id}"
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            approval_comment = f"Approved by {approver_name} at {timestamp}"
            if comment:
                approval_comment += f" - {comment}"
            
            update_data = {
                'approval': approval_status,
                'work_notes': approval_comment
            }
            
            update_response = requests.put(
                update_endpoint,
                auth=self.auth,
                headers=self.headers,
                json=update_data
            )
            update_response.raise_for_status()
            
            logger.info(f"Successfully updated approval status for ticket {ticket_number}")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error updating ticket approval: {str(e)}")
            return False

    def translate_firewall_changes(self, change_request_data):
        """
        Translate technical firewall changes to plain English.
        
        Args:
            change_request_data (dict): Change request data
            
        Returns:
            str: Plain English description of changes
        """
        # This is a simplified implementation
        # In a real system, this would use NLP and pattern matching
        # against the technical details in the change request
        
        description = change_request_data.get('description', '')
        short_desc = change_request_data.get('short_description', '')
        
        if 'firewall' in description.lower() or 'firewall' in short_desc.lower():
            # Extract potential IP addresses, ports, and services
            # This is a simplistic approach - real implementation would be more sophisticated
            plain_text = "This change will update the firewall rules to "
            
            if "allow" in description.lower():
                plain_text += "allow "
            elif "block" in description.lower():
                plain_text += "block "
            else:
                plain_text += "modify "
                
            # Add more context based on the description
            if "web" in description.lower():
                plain_text += "web traffic "
            elif "database" in description.lower():
                plain_text += "database connections "
            else:
                plain_text += "network traffic "
                
            # Add source/destination if available
            if "from" in description.lower() and "to" in description.lower():
                # Extract the from/to details - simplified implementation
                plain_text += "from the source to the destination systems."
            else:
                plain_text += "as specified in the technical details."
            
            return plain_text
        
        return "This change includes technical modifications to network settings. Please review the technical details."

# Example usage
if __name__ == "__main__":
    # Example credentials - in production, use environment variables or a secure vault
    instance = os.getenv("SERVICENOW_INSTANCE", "example.service-now.com")
    username = os.getenv("SERVICENOW_USERNAME", "admin")
    password = os.getenv("SERVICENOW_PASSWORD", "password")
    
    # Initialize connector
    connector = ServiceNowConnector(instance, username=username, password=password)
    
    # Get tickets for demo
    tickets = connector.get_my_tickets()
    
    if tickets:
        print(f"Found {len(tickets)} tickets:")
        for ticket in tickets:
            print(f"- {ticket['number']}: {ticket['short_description']}")
        
        # Get details for the first ticket
        first_ticket = tickets[0]['number']
        details = connector.get_ticket_details(first_ticket)
        
        if details:
            # Translate firewall changes to plain English
            plain_text = connector.translate_firewall_changes(details)
            print(f"\nPlain language description:\n{plain_text}")
            
            # Simulate approval
            connector.update_ticket_approval(
                first_ticket,
                "approved",
                "SecOps Engineer",
                "Approved via AI assistant"
            )
    else:
        print("No tickets found")
