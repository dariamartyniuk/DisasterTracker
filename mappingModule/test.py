from mappingModule.event_matcher import match_event_to_disasters

test_event = {
    "id": "1",
    "summary": "Trip to Kyiv",
    "location": "Kyiv, Ukraine",
    "start": {"date": "2025-04-01"},
    "end": {"date": "2025-04-07"}
}
result = match_event_to_disasters(test_event, distance_threshold=500)
print("Match result:", result)
