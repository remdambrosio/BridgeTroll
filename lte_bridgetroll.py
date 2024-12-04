#
# Title: lte_bridgetroll.py
# Authors: Rem D'Ambrosio
# Created: 2024-10-11
# Description: compares LTE traffic reported by JOVE vs. NERO
#

import re
import csv
import json
import argparse
import datetime

import sys
import os
sys.path.append(os.path.join('..', 'pythonAPIs'))

from JOVEAPI import JOVEAPI
from NEROAPI import NEROAPI


# ==================================================================================================
# MAIN
# ==================================================================================================


def main():
    """
    Run from terminal, ex:
    python3 lte_bridgetroll.py --report True --csv False
    """
    parser = argparse.ArgumentParser(description='compares LTE traffic, JOVE vs. NERO')
    parser.add_argument('-ff', '--from_file', action='store_true', help='use file, not API')
    parser.add_argument('-re', '--rep', action='store_true', help='write report to txt')
    parser.add_argument('-rp', '--rep_path', type=str, help='report path', default='data/lte_report.txt')
    parser.add_argument('-cs', '--csv', action='store_true', help='write data csv')
    parser.add_argument('-cp', '--csv_path', type=str, help='csv path', default='data/lte_data.csv')
    args = parser.parse_args()

    from_file = args.from_file
    rep_out = args.rep
    rep_path = args.rep_path
    csv_out = args.csv
    csv_path = args.csv_path

    jove_api = JOVEAPI()
    nero_api = NEROAPI()

    start_time = calc_start_of_month()

    lte_routers = {}
    if from_file:
        print("Reading JOVE and NERO data from local file...")
        lte_routers = read_data_from_file()
    else:
        print("Pulling JOVE and NERO data from API...")
        lte_routers = pull_jove_data(jove_api)
        lte_routers = pull_nero_data(nero_api, lte_routers, start_time)
        print("Writing updated data to file...")
        write_lte_routers(lte_routers)

    print("Comparing traffic data between sources...")
    results = compare_traffic(lte_routers)

    if rep_out:
        report_to_file(results, rep_path)
        print(f"=== Text Report saved to {rep_path} ===")

    if csv_out:
        csv_to_file(results, csv_path)
        print(f"=== Data CSV saved to {csv_path} ===")


# ==================================================================================================
# INPUTS
# ==================================================================================================


def read_data_from_file():
    """
    Reads offline archived data (originally pulled from JOVE and NERO)
    Output: dict of relevant devices with key = ICCID
    """
    with open('data/lte_offline_data.json', 'r', encoding='utf-8') as json_file:
        lte_routers = json.load(json_file)
    return lte_routers


def pull_jove_data(jove_api):
    """
    Pulls all relevant data from JOVE
    Output: dict with key = iccid, val = JOVE data for that device
    """
    lte_routers = {}

    recent_routers = jove_api.pull_recent()                   # get IDs for active routers

    count = 0
    for iccid in recent_routers.keys():                         # for each active router
        print(f"JOVE devices: {count}")
        if count > 500:
            break
        router_usage = jove_api.pull_current_usage(iccid)     # get LTE usage
        if router_usage['anon'] != 0:
            lte_routers[iccid] = {'jove_data':router_usage}
            count += 1

    return lte_routers


def pull_nero_data(nero_api, lte_routers, start_time):
    """
    Pulls all relevant data from NERO
    Input: dict with key = iccid
    Output: dict with key = iccid, with value now including NERO info
    """
    nero_routers = nero_api.pull_net_devices()

    count = 0
    for iccid, lte_router in list(lte_routers.items()):
        print(f"NERO devices: {count}")
        if iccid in nero_routers:
            if nero_routers[iccid]['anon'] == 'anon':
                nero_id = nero_routers[iccid]['id']
                nero_bytes = nero_api.pull_net_device_usage_since_date(nero_id, start_time)
                lte_router['nero_data'] = nero_routers[iccid]
                lte_router['nero_bytes'] = nero_bytes
        if 'nero_data' not in lte_router or 'nero_bytes' not in lte_router:
            lte_routers.pop(iccid)
        else:
            count += 1
            if count > 10:
                break
    return lte_routers


# ==================================================================================================
# CALCULATIONS
# ==================================================================================================


def calc_start_of_month():
    """
    Returns start of current month
    Output: str in format: %Y-%m-%dT%H:%M:%S%z
    """
    cur_time = datetime.datetime.now(datetime.timezone.utc)
    start_obj = datetime.datetime(cur_time.year, cur_time.month, 1, tzinfo=datetime.timezone.utc)
    start_time = start_obj.strftime('%Y-%m-%dT%H:%M:%S%z')
    return start_time


def check_for_router_name(string):
    """
    Checks if a string contains a valid router name
    Output: the router name (uppercase, excluding any other elements of input string), if it exists
    """
    input_string = string.upper()
    pattern = r'anon-regex'
    match = re.search(pattern, input_string)
    if match:
        return match.group(1)
    else:
        return None


def compare_traffic(lte_routers: dict):
    """
    does stuff
    """
    results = {}

    for router in lte_routers.values():
        if router['nero_data'] and router['jove_data']:
            name = router['nero_data']['anon']
            jove_usage = router['jove_data']['anon']
            nero_usage = router['nero_bytes']
            overage = jove_usage - nero_usage
            if nero_usage == 0:
                percentage = 'infinity'
            else:
                percentage = (overage / nero_usage) * 100

            results[name] = {'jove_usage':jove_usage,
                            'nero_usage':nero_usage,
                            'overage':overage,
                            'percentage':percentage}

    return results


# ==================================================================================================
# OUTPUTS
# ==================================================================================================


def write_lte_routers(lte_routers):
    """
    Writes relevant device data (pulled from JOVE and NERO) to local .json file
    Input: dict of relevant devices with key = ICCID
    """
    with open('data/lte_offline_data.json', 'w', encoding='utf-8') as json_file:
        json.dump(lte_routers, json_file, indent=4)
    return


def report_to_file(results: dict, rep_path: str):
    """
    Writes report to text file
    """
    report = "===== LTE Traffic Discrepancies: JOVE reporting >5% higher than NERO =====\n\n"

    for dev_name, dev_data in results.items():
        jove_usage = dev_data['jove_usage']
        nero_usage = dev_data['nero_usage']
        overage = dev_data['overage']
        percentage = dev_data['percentage']
        if percentage == 'infinity' or percentage > 5:
            report += f"""{dev_name}: JOVE = {jove_usage:.0f} bytes
            NERO = {nero_usage:.0f} bytes
            Overage (JOVE - NERO) = {overage:.0f} bytes
            Percentage (Overage / NERO) = {percentage}%\n\n"""

    with open(rep_path, 'w', encoding='utf-8') as file:
        file.write(report)

    return


def csv_to_file(results: dict, csv_path: str):
    """
    Writes data csv to file
    """
    head = ['name', 'MTD JOVE Usage', 'MTD NERO Usage',
            'Overage (JOVE-NC)', 'Percentage (Overage/NC)']
    with open(csv_path, mode='w', encoding='utf-8', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=head)
        writer.writeheader()
        for name, data in results.items():
            row = {
                'name': name,
                'MTD JOVE Usage': data['jove_usage'],
                'MTD NERO Usage': data['nero_usage'],
                'Overage (JOVE-NC)': data['overage'],
                'Percentage (Overage/NC)': data['percentage']
            }
            writer.writerow(row)
    return


if __name__ == '__main__':
    main()
