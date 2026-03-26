import Foundation

enum MockData {
    // Reference data — neighborhoods, disciplines, borough mappings.
    // These are not mock listings; they're used by the onboarding form
    // and filter logic regardless of where listings come from.

    /// Single sample listing used only for SwiftUI Previews.
    static let previewListing = StudioListing(
        id: UUID(),
        address: "Studio 107 · 1660 E New York Ave, Brooklyn, NY 11212",
        neighborhood: "Brooklyn",
        sqft: 170,
        monthlyRent: 850,
        photos: [],
        amenities: ["24/7 Access", "Natural Light"],
        leaseTermMonths: 12,
        availableDate: Date(),
        coTenantCompatibilityScore: 0.82,
        latitude: 40.6579,
        longitude: -73.9052,
        source: "rockella",
        sourceURL: "https://rockella.space/"
    )

    // MARK: - Neighborhoods (grouped by borough)

    /// All selectable neighborhoods, organized by borough for the picker UI.
    static let neighborhoodsByBorough: [(borough: String, neighborhoods: [String])] = [
        ("Manhattan", [
            "Alphabet City", "Chelsea", "Chinatown", "East Harlem", "East Village",
            "Financial District", "Flatiron", "Gramercy", "Greenwich Village",
            "Harlem", "Hell's Kitchen", "Inwood", "Little Italy", "Lower East Side",
            "Midtown", "Midtown East", "Murray Hill", "NoHo", "NoLita",
            "Roosevelt Island", "SoHo", "Tribeca", "Union Square",
            "Upper East Side", "Upper West Side", "Washington Heights", "West Village"
        ]),
        ("Brooklyn", [
            "Bay Ridge", "Bed-Stuy", "Boerum Hill", "Brooklyn Heights",
            "Bushwick", "Carroll Gardens", "Clinton Hill", "Cobble Hill",
            "Crown Heights", "DUMBO", "Downtown Brooklyn", "East New York",
            "East Williamsburg", "Flatbush", "Fort Greene", "Gowanus",
            "Greenpoint", "Park Slope", "Prospect Heights", "Prospect Lefferts Gardens",
            "Red Hook", "Sunset Park", "Williamsburg"
        ]),
        ("Queens", [
            "Astoria", "Bayside", "Corona", "East Elmhurst", "Elmhurst",
            "Far Rockaway", "Flushing", "Forest Hills", "Jackson Heights",
            "Jamaica", "Kew Gardens", "Long Island City", "Maspeth",
            "Rego Park", "Richmond Hill", "Ridgewood", "Sunnyside", "Woodside"
        ]),
        ("The Bronx", [
            "Concourse", "Fordham", "Hunts Point", "Kingsbridge",
            "Mott Haven", "Port Morris", "Riverdale", "South Bronx"
        ]),
        ("Staten Island", [
            "St. George", "Stapleton"
        ]),
    ]

    /// Flat list of all neighborhoods for convenience.
    static let neighborhoods: [String] = neighborhoodsByBorough.flatMap { $0.neighborhoods }

    /// All borough names.
    static let boroughs: [String] = neighborhoodsByBorough.map { $0.borough }

    /// Borough-level entries and their constituent neighborhoods — used for broad filtering.
    static let boroughNeighborhoods: [String: [String]] = {
        var dict: [String: [String]] = [:]
        for group in neighborhoodsByBorough {
            dict[group.borough] = group.neighborhoods
        }
        return dict
    }()

    /// Maps variant neighborhood names from the DB to canonical borough names.
    /// This handles "New York" → Manhattan, "Brooklyn" → Brooklyn, etc.
    static let neighborhoodToBoroughFallback: [String: String] = [
        "New York": "Manhattan",
        "NEW YORK": "Manhattan",
        "New york": "Manhattan",
        "New York City": "Manhattan",
        "NYC": "Manhattan",
        "NY": "Manhattan",
        "N.Y.": "Manhattan",
        "Brooklyn": "Brooklyn",
        "BROOKLYN": "Brooklyn",
        "brooklyn": "Brooklyn",
        "Queens": "Queens",
        "Bronx": "The Bronx",
        "BRONX": "The Bronx",
        "NewBronx": "The Bronx",
        "Staten Island": "Staten Island",
        "STATEN ISLAND": "Staten Island",
        "LIC": "Queens",
    ]

    static let disciplines: [String] = [
        "Painting",
        "Sculpture",
        "Photography",
        "Printmaking",
        "Ceramics",
        "Textile / Fiber Arts",
        "Installation Art",
        "Video / Film",
        "Performance Art",
        "Drawing",
        "Mixed Media",
        "Illustration",
        "Muralism",
        "Woodworking",
        "Metalworking",
        "Glassblowing",
        "Digital Art",
        "Sound Art",
        "Collage",
        "Other"
    ]

    static let mediationSessions: [MediationSession] = {
        let calendar = Calendar.current
        let now = Date()
        return [
            MediationSession(
                id: UUID(),
                date: calendar.date(byAdding: .day, value: 5, to: now) ?? now,
                topic: "Studio hours and noise boundaries",
                status: "Scheduled"
            ),
            MediationSession(
                id: UUID(),
                date: calendar.date(byAdding: .day, value: 18, to: now) ?? now,
                topic: "Shared supply storage arrangement",
                status: "Pending Confirmation"
            )
        ]
    }()
}
