from .models import RouteHalt
from datetime import timedelta

def get_segment_timing(train, source_station, destination_station):
    route = train.route
    
    station_sequence = []
    station_sequence.append({
        'station': route.source_station,
        'sequence': 0,
        'duration_from_start': timedelta(seconds=0)
    })
    
    for halt in RouteHalt.objects.filter(route=route).order_by('sequence_number'):
        station_sequence.append({
            'station': halt.station,
            'sequence': halt.sequence_number,
            'duration_from_start': halt.journey_duration_from_source
        })
    
    station_sequence.append({
        'station': route.destination_station,
        'sequence': len(station_sequence),
        'duration_from_start': route.journey_duration
    })
    
    source_timing = None
    destination_timing = None
    
    for station_item in station_sequence:
        if station_item['station'] == source_station:
            source_timing = station_item
        if station_item['station'] == destination_station:
            destination_timing = station_item
    
    if source_timing and destination_timing:
        segment_duration = destination_timing['duration_from_start'] - source_timing['duration_from_start']
        segment_departure = train.departure_date_time + source_timing['duration_from_start']
        segment_arrival = train.departure_date_time + destination_timing['duration_from_start']
        
        return {
            'segment_duration': segment_duration,
            'segment_departure': segment_departure,
            'segment_arrival': segment_arrival,
            'source_timing': source_timing,
            'destination_timing': destination_timing
        }
    
    return None 