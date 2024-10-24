#
# Title: bridgetroll.py
# Authors: Rem D'Ambrosio
# Created: 2024-08-27
# Description: compares traffic reported by Starlink vs. "Ares" (anonymized API)
#

import re
import csv
import json
import argparse
import datetime
import pytz

import sys
import os
sys.path.append(os.path.join('..', 'pythonAPIs'))

from StarlinkAPI import StarlinkAPI
from venusAPI import venusAPI
from aresAPI import aresAPI
from StarlinkRouter import StarlinkRouter


START_DATE = ''
END_DATE = ''


# ========================================================================================================================================================
# MAIN
# ========================================================================================================================================================


def main():
    parser = argparse.ArgumentParser(description='compares traffic reported by Starlink vs. Ares')
    parser.add_argument('-re', '--report', type=bool, help='write report to txt file', default=True)
    parser.add_argument('-rf', '--report_filename', type=str, help='filename/path for txt report output', default='report.txt')
    parser.add_argument('-cs', '--csv', type=bool, help='write data to csv file', default=True)
    parser.add_argument('-cf', '--csv_filename', type=str, help='filename/path for csv data output', default='data.csv')
    args = parser.parse_args()

    report_out = args.report
    report_filename = args.report_filename
    csv_out = args.csv
    csv_filename = args.csv_filename

    star_api = StarlinkAPI()
    venus_api = venusAPI()
    ares_api = aresAPI()

    print("Pulling routers and traffic from Starlink...")
    star_routers = get_star_routers(star_api)

    print("Pulling Starlink-connected interfaces from venus...")
    star_routers = get_venus_interfaces(venus_api, star_routers)

    print("Pulling traffic on interfaces from ares...")
    star_routers = get_ares_traffic(ares_api, star_routers)

    output_dict = {key: obj.__dict__ for key, obj in star_routers.items()}
    with open('output.json', 'w') as file:
        json.dump(output_dict, file, indent=4)

    print("Comparing Starlink and ares...")
    results = compare_traffic(star_routers)

    if report_out:
        report_to_file(results, report_filename)
        print(f"=== Text Report saved to {report_filename} ===")
    
    if csv_out:
        csv_to_file(results, csv_filename)
        print(f"=== Data CSV saved to {csv_filename} ===")

    return


# ========================================================================================================================================================
# PULLERS
# ========================================================================================================================================================


def get_star_routers(star_api):
    """
    Pulls from StarLink to populate a dict: key = nickname, value = StarlinkRouter object w/sln, starlink traffic populated
    """
    global START_DATE, END_DATE
    star_routers = {}
    page = 0
    last = False
    while (last == False):
        lines = star_api.get_service_lines(page)
        for line in lines['content']['results']:
            if line['active'] == True:
                sln = line['serviceLineNumber']
                star_name = line['nickname']
                if sln and star_name:
                    if router_search := re.search(r'-SK([^-]+)-', star_name):       # if standardized Starlink device w/router association
                        router_name = router_search.group(1).upper()
                        if usage_response := star_api.get_data_usage(sln):
                            star_traffic = usage_response['content']
                            sl_router = StarlinkRouter(name=router_name, star_sln=sln, star_traffic=star_traffic)
                            star_routers[router_name] = sl_router
                            if not START_DATE:                                      # using this pull, all start dates for billing period same across devices
                                START_DATE = sl_router.start_date                   # we will use this date to get data for the same period from other APIs
                                END_DATE = sl_router.end_date
        last = lines['content']['isLastPage']
        page += 1
    return star_routers


def get_venus_interfaces(venus_api, star_routers: dict):
    """
    Pulls from Venus API to find Starlink-connected interfaces on routers
    """
    venus_routers = venus_api.pull_routers()
    for venus_router in venus_routers:
        router_name = venus_router['name'].upper()
        if router_name in star_routers:
            if venus_router['links']:
                for link in venus_router['links']:
                    if link['isp'] == 'Starlink':
                        star_routers[router_name].venus_interface = link['interface']       # Ares API will need to know which interface is handling Starlink traffic
    return star_routers


def get_ares_traffic(ares_api, star_routers: dict):
    """
    Pulls from Ares API to get traffic through Starlink interfaces
    """
    start_date = None
    end_date = None

    if star_router := next(iter(star_routers.values()), None):      # if there are star_routers, use arbitrary one to set start/end date
        start_datetime = datetime.datetime.strptime(star_router.start_date, "%Y-%m-%d")
        end_datetime = datetime.datetime.strptime(star_router.end_date, "%Y-%m-%d")
        end_datetime = end_datetime - datetime.timedelta(days=1)    # ares dates are inclusive, while starlink excludes end date; remove it
        start_datetime = start_datetime.astimezone(pytz.utc)        # ares uses PST, starlink uses UTC; offset start and end
        end_datetime = end_datetime.astimezone(pytz.utc)
        start_date = start_datetime.strftime("%Y-%m-%d %H:%M:%S")   # back to strings, for ares pull
        end_date = end_datetime.strftime("%Y-%m-%d %H:%M:%S")

    function = f'anonymized Ares pull using {start_date} and {end_date} to get appropriate data'
    ares_traffic_all = ares_api.web_adb(function)
    lines = ares_traffic_all.splitlines()
    for line in lines:
        if line[8] == '-':
            line_router = line[:8].upper()
            if line_router in star_routers.keys():
                star_routers[line_router].ares_traffic += line
    return star_routers


# ========================================================================================================================================================
# REPORTER
# ========================================================================================================================================================


def compare_traffic(star_routers: dict):
    """
    Compares traffic between Starlink and Ares, writes result to dict
    """
    results = {}
    for name, router in star_routers.items():
        star_total, leeway = router.calc_star_total()
        ares_total = router.calc_ares_total()
        overage = star_total - ares_total
        if overage > 0:
            over_leeway = star_total - ares_total - leeway
            if over_leeway < 0:
                over_leeway = 0
        elif overage < 0:
            over_leeway = star_total - ares_total + leeway
            if over_leeway > 0:
                over_leeway = 0
        else:
            over_leeway = 0
        results[name] = {
            'star_total': star_total,
            'leeway': leeway,
            'ares_total': ares_total,
            'overage': overage,
            'over_leeway': over_leeway
        }

    return results


# ========================================================================================================================================================
# OUTPUTS
# ========================================================================================================================================================


def report_to_file(results: dict, report_filename: str):
    """
    Writes report to text file
    """
    global START_DATE, END_DATE
    report = f"===== Unexpected Traffic Discrepancies: {START_DATE} to {END_DATE} =====\n"
    for name, router in results.items():
        star_total = router['star_total'] or 0.00
        leeway = router['leeway'] or 0.00
        ares_total = router['ares_total'] or 0.00
        overage = router['overage'] or 0.00
        over_leeway = router['over_leeway'] or 0.00
        if over_leeway != 0:
            report += f"""=== {name} ===
    Starlink GB: {star_total:.4f}
    ares GB: {ares_total:.4f}
    Overage: {overage:.4f}
    Expected Leeway: {leeway:.4f}
    GB Over Expected: {over_leeway:.4f}
    """

    with open(report_filename, 'w') as file:
        file.write(report)
    return


def csv_to_file(results: dict, csv_filename: str):
    """
    Writes data csv to file
    """
    head = ['name', 'star_total', 'leeway', 'ares_total', 'overage', 'over_leeway']
    with open(csv_filename, mode='w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=head)
        writer.writeheader()
        for name, data in results.items():
            row = {
                'name': name,
                'star_total': f"{data['star_total']:.4f}",
                'leeway': f"{data['leeway']:.4f}",
                'ares_total': f"{data['ares_total']:.4f}",
                'overage': f"{data['overage']:.4f}",
                'over_leeway': f"{data['over_leeway']:.4f}"
            }
            writer.writerow(row)
    return


if __name__ == '__main__':
    main()