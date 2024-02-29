import time
import urllib3
import csv
import requests
import re
from requests.auth import HTTPBasicAuth
from ncclient import manager
from datetime import datetime
import logging
from config import connection_params_template, DNA_USER, DNA_PASS
from configDNA import DNA_FQDN, DNA_PORT, DNA_DEVICE_API

# Function to load switches from CSV
def load_switches_from_csv(csv_file):
    switches = []
    try:
        with open(csv_file, 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row['Hostname']:  # Check if the 'Hostname' field is not empty
                    switches.append(row['Hostname'])
        if not switches:
            print(f"No valid hostnames found in CSV file '{csv_file}'.")
            exit(1)
        return switches
    except FileNotFoundError:
        print(f"Error: CSV file '{csv_file}' not found.")
        exit(1)
    except csv.Error:
        print(f"Error: CSV file '{csv_file}' is corrupt.")
        exit(1)

# Load switches from CSV
DNA_SWITCHES = load_switches_from_csv('switches.csv')

# Configure logging
logging.basicConfig(filename='app.log', level=logging.INFO)

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Set headers for DNA Center API calls
headers = {'content-type': "application/json", 'x-auth-token': ""}

def spacer():
    print("+" + "-" * 45 + "+")

# Function for DNA Center authentication
def authenticate_dna():
    """Authenticates with DNA Center and retrieves authentication token."""
    url = f"https://{DNA_FQDN}:{DNA_PORT}/dna/system/api/v1/auth/token"
    try:
        response = requests.post(url, auth=HTTPBasicAuth(DNA_USER, DNA_PASS), headers=headers, verify=False)
        response.raise_for_status()
        token = response.json()["Token"]
        logging.info("Token found")
        return token
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to get DNA Center token: {e}")
        exit(1)

# Function to retrieve switch information
def get_switch_information(token):
    """Retrieves information about switches from DNA Center."""
    switch_details = []
    print(DNA_SWITCHES)
    for device in DNA_SWITCHES:
        print("Device:")
        print(device)
        url = f"https://{DNA_FQDN}:{DNA_PORT}{DNA_DEVICE_API}?hostname={device}"
        headers["x-auth-token"] = token
        try:
            response = requests.get(url, headers=headers, verify=False)
            response.raise_for_status()
            output = response.json()['response']
            for x in output:
                switch_details.append([x["id"], x["hostname"], x["managementIpAddress"], x["platformId"]])
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to retrieve information for switch {device}: {e}")
    return switch_details

# Function to connect to a device
def connect_to_device(device_params):
    """Establishes connection to a device."""
    try:
        logging.info(f"Connecting to {device_params['host']}...")
        return manager.connect(**{**connection_params_template, **device_params})
    except Exception as e:
        logging.error(f"Failed to connect to {device_params['host']}: {e}")
        return None

# Function to lock configuration on a device
def lock_configuration(device):
    """Locks the configuration on the device."""
    lock_supported = True
    tries = 0
    max_tries = 6
    seconds = 30
    while tries < max_tries:
        try:
            print("Locking device")
            spacer()
            device.lock(target='running')
            logging.info("Locked")
            return True
        except Exception as e:
            logging.warning("Locking not supported.")
            tries += 1
            print("Locking not supported. Retry in " + seconds + " seconds.")
            time.sleep(seconds)  # Wait for 5 minutes before retrying
    return False

# Function to unlock configuration on a device
def unlock_configuration(device):
    """Unlocks the configuration on the device."""
    try:
        print("Unlocking device")
        spacer()
        device.unlock(target='running')
        
        logging.info("Unlocked")
    except Exception as e:
        logging.error(f"Error unlocking configuration: {e}")

# Function to generate XML configuration for interfaces
def generate_xml_config():
    """Generates XML configuration for interfaces."""
    configXML = '''
        <config>
            <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
                <ip>
                    <access-list>
                        <standard xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-acl">
                            <name>21</name>
                            <access-list-seq-rule>
                                <sequence>10</sequence>
                                <permit>
                                <std-ace>
                                    <ipv4-prefix>10.18.87.89</ipv4-prefix>
                                </std-ace>
                                </permit>
                                <remark>CISCO_Collector</remark>
                            </access-list-seq-rule>
                            <access-list-seq-rule>
                                <sequence>20</sequence>
                                <permit>
                                <std-ace>
                                    <ipv4-prefix>10.20.16.41</ipv4-prefix>
                                </std-ace>
                                </permit>
                                <remark>DNA Center</remark>
                            </access-list-seq-rule>
                            <access-list-seq-rule>
                                <sequence>30</sequence>
                                <permit>
                                <std-ace>
                                    <ipv4-prefix>10.20.16.42</ipv4-prefix>
                                </std-ace>
                                </permit>
                            </access-list-seq-rule>
                            <access-list-seq-rule>
                                <sequence>40</sequence>
                                <permit>
                                <std-ace>
                                    <ipv4-prefix>10.20.16.43</ipv4-prefix>
                                </std-ace>
                                </permit>
                            </access-list-seq-rule>
                            <access-list-seq-rule>
                                <sequence>50</sequence>
                                <permit>
                                <std-ace>
                                    <ipv4-prefix>10.0.0.130</ipv4-prefix>
                                </std-ace>
                                </permit>
                                <remark>Nagios</remark>
                            </access-list-seq-rule>
                            <access-list-seq-rule>
                                <sequence>60</sequence>
                                <permit>
                                <std-ace>
                                    <ipv4-prefix>10.0.32.155</ipv4-prefix>
                                </std-ace>
                                </permit>
                                <remark>Cisco_ISE</remark>
                            </access-list-seq-rule>
                            <access-list-seq-rule>
                                <sequence>70</sequence>
                                <permit>
                                <std-ace>
                                    <ipv4-prefix>10.0.32.156</ipv4-prefix>
                                </std-ace>
                                </permit>
                            </access-list-seq-rule>
                            <access-list-seq-rule>
                                <sequence>80</sequence>
                                <permit>
                                <std-ace>
                                    <ipv4-prefix>10.100.185.30</ipv4-prefix>
                                </std-ace>
                                </permit>
                                <remark>Consola ART</remark>
                            </access-list-seq-rule>
                            <access-list-seq-rule>
                                <sequence>90</sequence>
                                <permit>
                                <std-ace>
                                    <ipv4-prefix>10.1.213.39</ipv4-prefix>
                                </std-ace>
                                </permit>
                                <remark>Area de Monitoreo</remark>
                            </access-list-seq-rule>
                            <access-list-seq-rule>
                                <sequence>100</sequence>
                                <permit>
                                <std-ace>
                                    <ipv4-prefix>10.1.213.41</ipv4-prefix>
                                </std-ace>
                                </permit>
                            </access-list-seq-rule>
                            <access-list-seq-rule>
                                <sequence>110</sequence>
                                <permit>
                                <std-ace>
                                    <ipv4-prefix>10.1.213.54</ipv4-prefix>
                                </std-ace>
                                </permit>
                            </access-list-seq-rule>
                            <access-list-seq-rule>
                                <sequence>120</sequence>
                                <permit>
                                <std-ace>
                                    <ipv4-prefix>10.1.213.56</ipv4-prefix>
                                </std-ace>
                                </permit>
                            </access-list-seq-rule>
                            <access-list-seq-rule>
                                <sequence>130</sequence>
                                <permit>
                                <std-ace>
                                    <ipv4-prefix>10.1.213.57</ipv4-prefix>
                                </std-ace>
                                </permit>
                            </access-list-seq-rule>
                        </standard>
                    </access-list>
                </ip>
                <line>
                    <vty xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0" nc:operation="replace">
                        <first nc:operation="replace">0</first>
                        <last nc:operation="replace">4</last>
                        <length nc:operation="replace">0</length>
                        <logging>
                        <synchronous/>
                        </logging>
                        <session-timeout nc:operation="replace">
                            <session-timeout-value>5</session-timeout-value>
                        </session-timeout>
                        <transport>
                        <input>
                            <input>ssh</input>
                        </input>
                        </transport>
                    </vty>
                    <vty xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0" nc:operation="replace">
                        <first nc:operation="replace">5</first>
                        <last nc:operation="replace">15</last>
                        <length nc:operation="replace">0</length>
                        <logging>
                        <synchronous/>
                        </logging>
                        <session-timeout nc:operation="replace">
                            <session-timeout-value>5</session-timeout-value>
                        </session-timeout>
                        <transport>
                        <input>
                            <input>ssh</input>
                        </input>
                        </transport>
                    </vty>
                </line>
                <ntp>
                    <server xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-ntp">
                        <server-list xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0" nc:operation="replace">
                            <ip-address>10.150.0.68</ip-address>
                        </server-list>
                        <server-list xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0" nc:operation="replace">
                            <ip-address>10.18.87.31</ip-address>
                        </server-list>
                        <server-list xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0" nc:operation="replace">                 
                            <ip-address>10.0.15.9</ip-address>
                        </server-list>
                        <server-list xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0" nc:operation="replace">
                            <ip-address>10.0.15.13</ip-address>
                        </server-list>
                    </server>
                </ntp>
            </native>
        </config>
    '''
    return configXML

# Function to apply configuration to a device
def apply_configuration(device, xml_config):
    """Applies the configuration to the device."""
    try:
        print("Applying configuration")
        spacer()
        device.edit_config(xml_config, target='running')
        return "Success", ""
    except Exception as e:
        return "Error", str(e)

# Function to close connection with a device
def close_connection(device):
    """Closes the session with the device."""
    device.close_session()
    logging.info("Connection closed.")
    print("Closing session")
    spacer()

# Function to write results to CSV file
def write_to_csv(filename, results):
    with open(filename, mode='a', newline='') as file:
        writer = csv.writer(file)
        for result in results:
            writer.writerow(result)

# Main function
def main():
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"netconf_results_{timestamp}.csv"

    # Authenticate with DNA Center
    token = authenticate_dna()

    # Retrieve switch information
    switches = get_switch_information(token)
    print("Switches:")
    print(switches)
    logging.info("Switches:")
    logging.info(switches)

    spacer()

    with open(filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Host", "Result", "Error"])

        for switch_info in switches:
            hostname, series, ip = switch_info[1], switch_info[3], switch_info[2]
            device_params = {'host': ip}  # Using IP address instead of hostname
            print("Connecting to "+ hostname)
            spacer()
            device = connect_to_device(device_params)
            if device:
                if lock_configuration(device):
                    print("Generating config")
                    xml_config = generate_xml_config()  # Passing switch_ports for XML generation
                    spacer()
                    result, error = apply_configuration(device, xml_config)
                    unlock_configuration(device)
                    writer.writerow([hostname, result, error])
                    spacer()
                else:
                    writer.writerow([hostname, "Unable to lock configuration", ""])
                close_connection(device)
            else:
                writer.writerow([hostname, "Failed to connect to the device", ""])

    logging.info(f"Results saved to {filename}")

if __name__ == "__main__":
    main()
