"""
PropertyKING — Constants
Default values and constant definitions.
"""

# Default Property Types (seeded on first run)
DEFAULT_PROPERTY_TYPES = [
    {"name": "House", "icon": "🏠", "description": "Single family residential home", "order": 1},
    {"name": "Condo", "icon": "🏢", "description": "Condominium unit", "order": 2},
    {"name": "Townhouse", "icon": "🏘️", "description": "Townhouse or row house", "order": 3},
    {"name": "Apartment", "icon": "🏬", "description": "Apartment unit", "order": 4},
    {"name": "Villa", "icon": "🏡", "description": "Luxury villa property", "order": 5},
    {"name": "Multi-Family", "icon": "🏗️", "description": "Multi-family residential building", "order": 6},
    {"name": "Land", "icon": "🌾", "description": "Vacant land or lot", "order": 7},
    {"name": "Commercial", "icon": "🏪", "description": "Commercial property", "order": 8},
    {"name": "Mobile Home", "icon": "🏕️", "description": "Mobile or manufactured home", "order": 9},
    {"name": "Farm/Ranch", "icon": "🌿", "description": "Farm, ranch, or agricultural property", "order": 10},
]

# Default Amenities (seeded on first run)
DEFAULT_AMENITIES = [
    # Indoor
    {"name": "Central AC", "icon": "❄️", "category": "indoor", "order": 1},
    {"name": "Heating", "icon": "🔥", "category": "indoor", "order": 2},
    {"name": "Fireplace", "icon": "🪵", "category": "indoor", "order": 3},
    {"name": "Hardwood Floors", "icon": "🪵", "category": "indoor", "order": 4},
    {"name": "Walk-in Closet", "icon": "👔", "category": "indoor", "order": 5},
    {"name": "In-unit Laundry", "icon": "👕", "category": "indoor", "order": 6},
    {"name": "Dishwasher", "icon": "🍽️", "category": "indoor", "order": 7},
    {"name": "Smart Home", "icon": "📱", "category": "indoor", "order": 8},
    {"name": "High Ceilings", "icon": "📐", "category": "indoor", "order": 9},
    {"name": "Updated Kitchen", "icon": "🍳", "category": "indoor", "order": 10},

    # Outdoor
    {"name": "Swimming Pool", "icon": "🏊", "category": "outdoor", "order": 11},
    {"name": "Hot Tub", "icon": "🛁", "category": "outdoor", "order": 12},
    {"name": "Garden/Yard", "icon": "🌻", "category": "outdoor", "order": 13},
    {"name": "Patio/Deck", "icon": "🪑", "category": "outdoor", "order": 14},
    {"name": "Balcony", "icon": "🌇", "category": "outdoor", "order": 15},
    {"name": "BBQ Area", "icon": "🍖", "category": "outdoor", "order": 16},
    {"name": "Outdoor Kitchen", "icon": "🍳", "category": "outdoor", "order": 17},

    # Community
    {"name": "Gym/Fitness", "icon": "💪", "category": "community", "order": 18},
    {"name": "Clubhouse", "icon": "🏛️", "category": "community", "order": 19},
    {"name": "Tennis Court", "icon": "🎾", "category": "community", "order": 20},
    {"name": "Dog Park", "icon": "🐕", "category": "community", "order": 21},
    {"name": "Playground", "icon": "🛝", "category": "community", "order": 22},
    {"name": "Concierge", "icon": "🛎️", "category": "community", "order": 23},
    {"name": "EV Charging", "icon": "🔌", "category": "community", "order": 24},

    # Security
    {"name": "Gated Community", "icon": "🚧", "category": "security", "order": 25},
    {"name": "Security System", "icon": "🔒", "category": "security", "order": 26},
    {"name": "Doorman", "icon": "🚪", "category": "security", "order": 27},
    {"name": "Security Camera", "icon": "📹", "category": "security", "order": 28},

    # Utilities
    {"name": "Solar Panels", "icon": "☀️", "category": "utilities", "order": 29},
    {"name": "Water Well", "icon": "💧", "category": "utilities", "order": 30},
    {"name": "Septic System", "icon": "🔧", "category": "utilities", "order": 31},
    {"name": "High-Speed Internet", "icon": "📡", "category": "utilities", "order": 32},

    # Accessibility
    {"name": "Wheelchair Access", "icon": "♿", "category": "accessibility", "order": 33},
    {"name": "Elevator", "icon": "🛗", "category": "accessibility", "order": 34},
    {"name": "Single Story", "icon": "🏠", "category": "accessibility", "order": 35},
]

# US States
US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia"
}
