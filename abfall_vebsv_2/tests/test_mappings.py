
import unittest
import uuid
from datetime import datetime
import sys
import os

# Add the models/library directory to path to allow direct import of mappings
# bypassing the top-level models package which requires Odoo
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../models/library')))

from mappings import Shipment, PlannedWaypoint, Period, ShipmentItem, NetProperty

class TestMappings(unittest.TestCase):
    def test_shipment_parse_sms_solution(self):
        # Setup
        pickup_period = Period(datetime.now(), datetime.now())
        dropoff_period = Period(datetime.now(), datetime.now())
        
        pickup_waypoint = PlannedWaypoint(
            period=pickup_period,
            location_internal_id="pickup_loc_id",
            party_internal_id="pickup_party_id"
        )
        
        dropoff_waypoint = PlannedWaypoint(
            period=dropoff_period,
            location_internal_id="dropoff_loc_id", # Distinct ID
            party_internal_id="dropoff_party_id"   # Distinct ID
        )
        
        shipment = Shipment(
            shipment_uuid=uuid.uuid4(),
            internal_id="shipment_123",
            shipment_items=[],
            pickup_site_service=pickup_waypoint,
            drop_of_site_service=dropoff_waypoint
        )
        
        # Execute
        result = shipment.parse(sms_solution=True)
        
        # Verify PickUpSiteService
        self.assertIn('PickUpSiteService', result)
        self.assertEqual(
            result['PickUpSiteService']['SiteLocalUnitReferenceID'],
            "pickup_loc_id"
        )
        
        # Verify DropOffSiteService
        self.assertIn('DropOffSiteService', result)
        # This assertions should FAIL before the fix because it was using pickup_site_service
        self.assertEqual(
            result['DropOffSiteService']['SiteLocalUnitReferenceID'],
            "dropoff_loc_id",
            "DropOffSiteService should use drop-off location ID, not pickup location ID"
        )

if __name__ == '__main__':
    unittest.main()
