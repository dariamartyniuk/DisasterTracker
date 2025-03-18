from mappingModule.event_matcher import fetch_disaster_events

disasters = fetch_disaster_events()
print(f"Disaster Events: {disasters}")
