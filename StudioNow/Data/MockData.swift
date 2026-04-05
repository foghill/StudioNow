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

    // MARK: - Sample listings (screenshot / preview fallback)

    /// Rich sample listings used for App Store screenshots and SwiftUI previews.
    /// Loaded by AppState when the API returns zero results (e.g. during screenshot builds).
    static let sampleListings: [StudioListing] = {
        let now = Date()
        let cal = Calendar.current
        func daysOut(_ n: Int) -> Date { cal.date(byAdding: .day, value: n, to: now) ?? now }
        return [
            StudioListing(
                id: UUID(),
                address: "Studio 3B · 540 W 26th St, Chelsea, NY 10001",
                neighborhood: "Chelsea",
                sqft: 320,
                monthlyRent: 2200,
                photos: [],
                amenities: ["24/7 Access", "Natural Light", "Freight Elevator", "Climate Control"],
                leaseTermMonths: 12,
                availableDate: daysOut(14),
                coTenantCompatibilityScore: 0.91,
                latitude: 40.7490, longitude: -74.0040,
                source: "spacefinder", sourceURL: ""
            ),
            StudioListing(
                id: UUID(),
                address: "Unit 12 · 1000 Dean St, Crown Heights, NY 11238",
                neighborhood: "Crown Heights",
                sqft: 250,
                monthlyRent: 1400,
                photos: [],
                amenities: ["24/7 Access", "Shared Kiln", "Loading Dock"],
                leaseTermMonths: 12,
                availableDate: daysOut(7),
                coTenantCompatibilityScore: 0.85,
                latitude: 40.6701, longitude: -73.9478,
                source: "nyfa", sourceURL: ""
            ),
            StudioListing(
                id: UUID(),
                address: "Studio 204 · 1 Mifflin Place, Bushwick, NY 11221",
                neighborhood: "Bushwick",
                sqft: 180,
                monthlyRent: 950,
                photos: [],
                amenities: ["Natural Light", "Shared Bathroom", "Ground Floor"],
                leaseTermMonths: 6,
                availableDate: daysOut(30),
                coTenantCompatibilityScore: nil,
                latitude: 40.7048, longitude: -73.9219,
                source: "listings_project", sourceURL: ""
            ),
            StudioListing(
                id: UUID(),
                address: "Floor 3 · 21-23 47th Ave, Long Island City, NY 11101",
                neighborhood: "Long Island City",
                sqft: 450,
                monthlyRent: 2800,
                photos: [],
                amenities: ["24/7 Access", "Skylight", "Loading Dock", "Freight Elevator"],
                leaseTermMonths: 24,
                availableDate: daysOut(45),
                coTenantCompatibilityScore: 0.78,
                latitude: 40.7440, longitude: -73.9484,
                source: "coworker", sourceURL: ""
            ),
            StudioListing(
                id: UUID(),
                address: "Rm 5A · 2500 Boston Rd, Bronx, NY 10467",
                neighborhood: "Mott Haven",
                sqft: 200,
                monthlyRent: 800,
                photos: [],
                amenities: ["24/7 Access", "Street Level"],
                leaseTermMonths: 12,
                availableDate: daysOut(21),
                coTenantCompatibilityScore: nil,
                latitude: 40.8448, longitude: -73.8648,
                source: "nyc_opendata", sourceURL: ""
            ),
            StudioListing(
                id: UUID(),
                address: "Studio 6 · 100 Myrtle Ave, Fort Greene, NY 11201",
                neighborhood: "Fort Greene",
                sqft: 290,
                monthlyRent: 1750,
                photos: [],
                amenities: ["Natural Light", "Central HVAC", "Shared Kitchen"],
                leaseTermMonths: 12,
                availableDate: daysOut(10),
                coTenantCompatibilityScore: 0.88,
                latitude: 40.6897, longitude: -73.9747,
                source: "rockella", sourceURL: ""
            ),
            StudioListing(
                id: UUID(),
                address: "4th Floor · 93 2nd Ave, East Village, NY 10003",
                neighborhood: "East Village",
                sqft: 140,
                monthlyRent: 1600,
                photos: [],
                amenities: ["Natural Light", "Quiet Building"],
                leaseTermMonths: 12,
                availableDate: daysOut(3),
                coTenantCompatibilityScore: 0.72,
                latitude: 40.7265, longitude: -73.9879,
                source: "spacefinder", sourceURL: ""
            ),
            StudioListing(
                id: UUID(),
                address: "Unit 2C · 120 Greenpoint Ave, Greenpoint, NY 11222",
                neighborhood: "Greenpoint",
                sqft: 210,
                monthlyRent: 1300,
                photos: [],
                amenities: ["Skylight", "Shared Storage", "Bike Room"],
                leaseTermMonths: 12,
                availableDate: daysOut(18),
                coTenantCompatibilityScore: nil,
                latitude: 40.7296, longitude: -73.9551,
                source: "listings_project", sourceURL: ""
            ),
            StudioListing(
                id: UUID(),
                address: "Bay 7 · 33 Eagle St, Red Hook, NY 11231",
                neighborhood: "Red Hook",
                sqft: 600,
                monthlyRent: 3200,
                photos: [],
                amenities: ["24/7 Access", "Loading Bay", "High Ceilings", "3-Phase Power"],
                leaseTermMonths: 24,
                availableDate: daysOut(60),
                coTenantCompatibilityScore: 0.95,
                latitude: 40.6745, longitude: -74.0093,
                source: "navy_yard", sourceURL: ""
            ),
            StudioListing(
                id: UUID(),
                address: "Studio 101 · 4415 Broadway, Washington Heights, NY 10040",
                neighborhood: "Washington Heights",
                sqft: 175,
                monthlyRent: 900,
                photos: [],
                amenities: ["24/7 Access", "Natural Light"],
                leaseTermMonths: 12,
                availableDate: daysOut(12),
                coTenantCompatibilityScore: nil,
                latitude: 40.8434, longitude: -73.9395,
                source: "nyfa", sourceURL: ""
            ),
        ]
    }()

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
