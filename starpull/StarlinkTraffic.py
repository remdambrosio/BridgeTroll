#
# Title: StarlinkRouter.py
# Authors: Rem D'Ambrosio
# Created: 2024-10-23
# Description: stores traffic info for a Starlink device
#

class StarlinkTraffic:

    def __init__(self,
                 name: str = '',
                 sln: str = '',
                 months: dict = None
                 ):
        
        self.name = name
        self.sln = sln
        self.months = months if months is not None else {}

