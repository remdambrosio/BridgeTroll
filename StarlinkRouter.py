#
# Title: StarlinkRouter.py
# Authors: Rem D'Ambrosio
# Created: 2024-08-28
# Description: stores info relating to a Starlink-connected router
#

import re

class StarlinkRouter:

    def __init__(self,
                 name: str = '',
                 star_sln: str = '',
                 star_traffic: dict = {},
                 venus_interface: str = '',
                 ares_traffic: str = '',
                 ):
        
        self.name = name
        self.star_sln = star_sln
        self.star_traffic = star_traffic
        
        self.start_date, self.end_date = self.set_dates()

        self.venus_interface = venus_interface
        self.ares_traffic = ares_traffic


    def set_dates(self):
        cycle = min(self.star_traffic['billingCycles'], key=lambda x: x['startDate'])   # only want first/earliest billing cycle in returned data
        start_date = (cycle['startDate'])[:10]
        end_date = (cycle['endDate'])[:10]
        return start_date, end_date


    def calc_star_total(self): 
        star_total = 0
        leeway = 1                                                                      # base leeway reckoned as 1 GB (rounding up total)
        cycle = min(self.star_traffic['billingCycles'], key=lambda x: x['startDate'])   # only want first/earliest billing cycle in returned data
        for day in cycle['dailyDataUsages']:
            for bin in day['dataUsageBins']:
                star_total += bin['totalGB']
                leeway += 0.01                                                          # possible rounding up per bin adds leeway
        return star_total, leeway


    def calc_ares_total(self):
        ares_total = 0
        if in_search := re.search(fr',{self.venus_interface},IF-MIB\.ifHCInOctets,=,(\d+)', self.ares_traffic):
            ares_total += float(in_search.group(1)) * 0.000000001
        if out_search := re.search(fr',{self.venus_interface},IF-MIB\.ifHCOutOctets,=,(\d+)', self.ares_traffic):
            ares_total += float(out_search.group(1)) * 0.000000001
        return ares_total