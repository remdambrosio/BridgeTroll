#
# Title: starpull.py
# Authors: Rem D'Ambrosio
# Created: 2024-10-22
# Description: simple pull of all traffic data for all starlinks in last 6 months
#

import csv
import json
import argparse
import datetime

import sys
import os
sys.path.append(os.path.join('..', '..', 'pythonAPIs'))

from StarlinkAPI import StarlinkAPI
from StarlinkTraffic import StarlinkTraffic


# ========================================================================================================================================================
# MAIN
# ========================================================================================================================================================


def main():
    parser = argparse.ArgumentParser(description='compares traffic reported by Starlink vs. AKIPS')
    parser.add_argument('-cc', '--cycle_count', type=str, help='how many cycles to retrieve', default=7)
    parser.add_argument('-cf', '--csv_filename', type=str, help='filename/path for csv data output', default='starlink_traffic')
    args = parser.parse_args()

    cycle_count = args.cycle_count
    csv_filename = args.csv_filename

    star_api = StarlinkAPI()

    print("Pulling traffic from Starlink...")
    star_traffic = get_star_traffic(star_api, cycle_count)

    print("Writing to CSV...")
    to_csv_file_simple(star_traffic, csv_filename)

    print(f"=== Data saved to CSV ===")

    return


# ========================================================================================================================================================
# PULLERS
# ========================================================================================================================================================


def get_star_traffic(star_api, cycle_count):
    """
    Pulls from StarLink to populate a dict: key = sln, value = StarlinkTraffic object
    """
    star_traffic = {}
    page_number = 0
    last = False
    while (last == False):
        page = star_api.get_data_usage_cycles(cycle_count=cycle_count, page=page_number)
        with open('test.json', 'w') as f:
            json.dump(page, f, indent=4)
        for device in page['content']['results']:

            sln = device['serviceLineNumber']
            if sln not in star_traffic:
                star_traffic[sln] = StarlinkTraffic(sln=sln)

            for cycle in device['billingCycles']:
                
                start_date = cycle['startDate']
                month_name = datetime.datetime.fromisoformat(start_date.replace("Z", "+00:00")).strftime("%B")

                if month_name not in star_traffic[sln].months:
                    star_traffic[sln].months[month_name] = {'Priority':0, 'Standard':0, 'Opt-In Priority':0}

                star_traffic[sln].months[month_name]['Priority'] += cycle['totalPriorityGB']
                star_traffic[sln].months[month_name]['Standard'] += cycle['totalStandardGB']
                star_traffic[sln].months[month_name]['Opt-In Priority'] += cycle['totalOptInPriorityGB']

        last = page['content']['isLastPage']
        page_number += 1

    return star_traffic


# ========================================================================================================================================================
# OUTPUTS
# ========================================================================================================================================================


def to_csv_file_billing(star_traffic: dict, csv_filename: str):
    """
    Writes data to csv files, one for each month, with columns for each billing type
    """
    head = ['SLN', 'Priority', 'Standard', 'Opt-In Priority']
    data_by_month = {}

    for sln, traffic in star_traffic.items():
        for month_name, month_data in traffic.months.items():
            if month_name not in data_by_month:
                data_by_month[month_name] = []
            data_by_month[month_name].append({
                'SLN': sln,
                'Priority': f"{month_data['Priority']:.4f}",
                'Standard': f"{month_data['Standard']:.4f}",
                'Opt-In Priority': f"{month_data['Opt-In Priority']:.4f}"
            })

    for month_name, rows in data_by_month.items():
        filename = f"{csv_filename}_{month_name}.csv"
        with open(filename, mode='w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=head)
            writer.writeheader()
            writer.writerows(rows)

    return


def to_csv_file_compact(star_traffic: dict, csv_filename: str):
    """
    Writes data to csv file, with columns for each month/data type pairing
    """
    head = ['SLN']
    data_by_sln = {}
    month_names = set()
    
    for sln, traffic in star_traffic.items():
        if sln not in data_by_sln:
            data_by_sln[sln] = {}
        for month_name, month_data in traffic.months.items():
            month_names.add(month_name)
            data_by_sln[sln][month_name] = {
                'Priority': f"{month_data['Priority']:.4f}",
                'Standard': f"{month_data['Standard']:.4f}",
                'Opt-In Priority': f"{month_data['Opt-In Priority']:.4f}"
            }

    month_names = sorted(month_names)

    for month in month_names:
        head.append(f"{month} - Priority")
        head.append(f"{month} - Standard")
        head.append(f"{month} - Opt-In Priority")

    rows = []
    for sln, months in data_by_sln.items():
        row = [sln]
        for month in month_names:
            if month in months:
                row.append(months[month]['Priority'])
                row.append(months[month]['Standard'])
                row.append(months[month]['Opt-In Priority'])
            else:
                row.extend(['0.0000', '0.0000', '0.0000'])
        rows.append(row)

    filename = csv_filename + '_compact.csv'
    with open(filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(head)
        writer.writerows(rows)

    return


def to_csv_file_simple(star_traffic: dict, csv_filename: str):
    """
    Writes data to a single CSV file, with columns for each month
    """
    data_by_sln = {}

    for sln, traffic in star_traffic.items():
        data_by_sln[sln] = {
            month_name: f"{month_data['Priority'] + month_data['Standard'] + month_data['Opt-In Priority']:.4f}"
            for month_name, month_data in traffic.months.items()
        }

    month_order = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]
    month_names = [month for month in month_order if month in set(month for months in data_by_sln.values() for month in months)]
    header = ['SLN'] + month_names

    rows = [
        [sln] + [data_by_sln[sln].get(month, '0.0000') for month in month_names]
        for sln in data_by_sln
    ]

    filename = csv_filename + '_simple.csv'
    with open(filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(header)
        writer.writerows(rows)

    return


if __name__ == '__main__':
    main()