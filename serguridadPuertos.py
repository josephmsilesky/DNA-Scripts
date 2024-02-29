import time
import urllib3
import csv
import requests
import re
from requests.auth import HTTPBasicAuth
from ncclient import manager
from datetime import datetime
from config import connection_params_template,DNA_USER, DNA_PASS
from configDNA import DNA_FQDN, DNA_PORT, DNA_DEVICE_API, DNA_INTERFACE_API

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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



# Set headers for DNA Center API calls
headers = {'content-type': "application/json", 'x-auth-token': ""}

def spacer():
    print("+" + "-" * 45 + "+")

# Function to get DNA Center token
def dnac_token():
    url = f"https://{DNA_FQDN}:{DNA_PORT}/dna/system/api/v1/auth/token"
    try:
        response = requests.post(url, auth=HTTPBasicAuth(DNA_USER, DNA_PASS), headers=headers, verify=False)
        response.raise_for_status()
        token = response.json()["Token"]
        print("Token found")
        return token
    except requests.exceptions.RequestException as e:
        print(f"Failed to get DNA Center token: {e}")
        exit(1)

# Function to get switches information
def get_switches(token):
    switch_details = []
    for device in DNA_SWITCHES:
        url = f"https://{DNA_FQDN}:{DNA_PORT}{DNA_DEVICE_API}?hostname={device}"
        headers["x-auth-token"] = token
        try:
            response = requests.get(url, headers=headers, verify=False)
            response.raise_for_status()
            output = response.json()['response']
            for x in output:
                switch_details.append([x["id"], x["hostname"], x["managementIpAddress"], x["platformId"]])
        except requests.exceptions.RequestException as e:
            print(f"Failed to retrieve information for switch {device}: {e}")
    return switch_details

# Function to get network interfaces
def network_interfaces(token, id, hostname, series):
    ports = []
    total_ports = []
    switch_info = []
    url = "https://{}:{}{}{}".format(DNA_FQDN, DNA_PORT, DNA_INTERFACE_API, id)
    headers["x-auth-token"] = token
    response = requests.get(url, headers=headers, verify=False)
    output = response.json()['response']

    for interface in output:
        if interface["interfaceType"] == "Physical":
            port_name = interface["portName"]
            if port_name.startswith("GigabitEthernet1/0/") and port_name.endswith(tuple(map(str, range(1, 49)))) and not any(
                    substring in port_name for substring in ["Loopback", "Vlan", "Bluetooth", "App"]):
                if "portMode" in interface and interface["portMode"] == "access":
                    print("Interface Name:", port_name)
                    result = re.search(r'\d+/\d+/(\d+)', port_name)
                    if result:
                        desired_part = result.group(0)
                        ports.append(desired_part)

    switch_info.insert(0, hostname)
    switch_info.insert(1, series)
    total_ports = (len(ports))

    return switch_info, total_ports, ports, response


def get_Interfaces(switches, token):
    switch_port = []
    for switch in switches:
        print(switch)
        spacer()
        try:
            id, hostname, ip, platform = switch
            print("Interfaces:\n")
            interfaces = network_interfaces(token, id, hostname, platform)
            switch_port.append(interfaces[2])
            info = interfaces[0]
            total = interfaces[1]
            access = interfaces[2]

        except Exception as e:
            switch_port.append([])
    return switch_port



    
# Function to connect to a device
def connect_to_device(device_params):
    """Establishes connection to a device."""
    try:
        print(f"Connecting to {device_params['host']}...")
        return manager.connect(**{**connection_params_template, **device_params})
    except Exception as e:
        print(f"Failed to connect to {device_params['host']}: {e}")
        return None

# Function to lock configuration on a device
def lock_configuration(device):
    """Locks the configuration on the device."""
    lock_supported = True
    tries = 0
    max_tries = 6
    while tries < max_tries:
        try:
            device.lock(target='running')
            print("Locked")
            return True
        except Exception as e:
            print("Locking not supported. Skipping locking.")
            tries += 1
            time.sleep(30)  # Wait for 5 minutes before retrying
    return False

# Function to unlock configuration on a device
def unlock_configuration(device):
    """Unlocks the configuration on the device."""
    try:
        device.unlock(target='running')
        print("Unlocked")
    except Exception as e:
        print(f"Error unlocking configuration: {e}")

# Function to generate XML configuration for interfaces
def generate_XML(ports):
    """Generates XML configuration for the given interfaces."""
    interface_template = '''
        <interface>
            <GigabitEthernet>
                <name>{interface_name}</name>
            <switchport>
            <mode xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-switch">
                <access/>
            </mode>
            <nonegotiate xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-switch"/>
            <port-security-cfg xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-switch"/>
            <port-security-conf xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-switch">
                <port-security>
                <maximum>
                    <max-addresses>3</max-addresses>
                </maximum>
                </port-security>
            </port-security-conf>
            <port-security xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-switch">
                <maximum>
                <max-addresses>3</max-addresses>
                </maximum>
            </port-security>
            </switchport>
            <logging>
            <event>
                <link-status/>
            </event>
            </logging>
            <access-session>
            <closed/>
            <port-control-config>auto</port-control-config>
            <port-control>
                <auto/>
            </port-control>
            <control-direction-config>in</control-direction-config>
            <control-direction>
                <in/>
            </control-direction>
            </access-session>
            <trust>
            <device>cisco-phone</device>
            </trust>
            <cdp xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-cdp">
            <tlv>
                <app/>
                <server-location/>
                <location/>
            </tlv>
            </cdp>
            <dot1x xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-dot1x">
            <pae>authenticator</pae>
            <timeout>
                <tx-period>5</tx-period>
            </timeout>
            </dot1x>
            <service-policy xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-policy">
            <input>AutoQos-4.0-CiscoPhone-Input-Policy</input>
            <output>AutoQos-4.0-Output-Policy</output>
            <type>
                <control>
                <subscriber>DOT1X-MAB</subscriber>
                </control>
            </type>
            </service-policy>
            <authentication xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-sanet">
            <periodic/>
            </authentication>
            <mab xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-sanet"/>
            <spanning-tree xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-spanning-tree">
            <portfast/>
            </spanning-tree>
            <auto xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-switch">
            <qos>
                <voip>
                <cisco-phone/>
                </voip>
            </qos>
            </auto>
            <device-tracking xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-switch"/>
            </GigabitEthernet>
        </interface>
    '''
    return '''
        <config>
            <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
                {}
            </native>
        </config>
    '''.format(''.join(interface_template.format(interface_name=interface_name) for interface_name in ports))



# Function to apply configuration to a device
def apply_configuration(device, xml_config):
    """Applies the configuration to the device."""
    try:
        device.edit_config(xml_config, target='running')
        return "Success"
    except Exception as e:
        return f"Error: {e}"

# Function to close connection with a device
def close_connection(device):
    """Closes the session with the device."""
    device.close_session()
    print("Connection closed.")

# Main script
def main():
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"netconf_results_{timestamp}.csv"

    # GET DNA TOKEN
    token = dnac_token()

    # GET SWITCHES INFORMATION
    switches = get_switches(token)
    print("Switches:")
    print(switches)

    # GET PORTS INFORMATION
    ports = get_Interfaces(switches, token)

    print("Ports:")
    print(ports)

    spacer()

    with open(filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Host", "Result", "Error"])

        for switch_info, switch_ports in zip(switches, ports):
            hostname, series, ip = switch_info[1], switch_info[3], switch_info[2]
            device_params = {'host': ip}  # Using IP address instead of hostname
            device = connect_to_device(device_params)
            if device:
                if lock_configuration(device):
                    xml_config = generate_XML(switch_ports)  # Passing switch_ports for XML generation
                    result = apply_configuration(device, xml_config)
                    unlock_configuration(device)
                    writer.writerow([hostname, result, ""])
                else:
                    writer.writerow([hostname, "Unable to lock configuration", ""])
                close_connection(device)
            else:
                writer.writerow([hostname, "Failed to connect to the device", ""])

    print(f"Results saved to {filename}")

if __name__ == "__main__":
    main()
