import Foundation

struct ArtistProfile: Codable, Identifiable {
    var id: UUID = UUID()
    var name: String
    var discipline: String
    var portfolioURL: String?
}

struct StudioNeeds: Codable {
    var minSqft: Int
    var maxSqft: Int
    var neighborhoods: [String]
    var maxMonthlyBudget: Int
    var leaseStart: Date
    var leaseDurationMonths: Int
    var openToCoTenants: Bool
}

struct StudioListing: Codable, Identifiable {
    var id: UUID = UUID()
    var address: String
    var neighborhood: String
    var sqft: Int
    var monthlyRent: Int
    var photos: [String]
    var amenities: [String]
    var leaseTermMonths: Int
    var availableDate: Date
    var coTenantCompatibilityScore: Double?
    var latitude: Double
    var longitude: Double
}

enum ApplicationStatus: String, Codable, CaseIterable {
    case notStarted = "Not Started"
    case submitted = "Submitted"
    case underReview = "Under Review"
    case approved = "Approved"
    case active = "Active"

    var icon: String {
        switch self {
        case .notStarted: return "circle"
        case .submitted: return "paperplane.fill"
        case .underReview: return "magnifyingglass"
        case .approved: return "checkmark.seal.fill"
        case .active: return "key.fill"
        }
    }

    var description: String {
        switch self {
        case .notStarted: return "You haven't applied for a space yet."
        case .submitted: return "Your application has been submitted. We'll review it shortly."
        case .underReview: return "Our team is reviewing your application."
        case .approved: return "Congratulations! Your application has been approved."
        case .active: return "Your lease is active. Welcome to your new studio!"
        }
    }
}

struct MediationSession: Codable, Identifiable {
    var id: UUID = UUID()
    var date: Date
    var topic: String
    var status: String
}

// MARK: - API response types

struct APIListingsResponse: Decodable {
    let total: Int
    let listings: [RemoteListing]
}

struct RemoteLeaseTerms: Decodable {
    let minMonths: Int?
    let maxMonths: Int?
    let availableDate: String?
    let sharedOk: Bool?

    enum CodingKeys: String, CodingKey {
        case minMonths = "min_months"
        case maxMonths = "max_months"
        case availableDate = "available_date"
        case sharedOk = "shared_ok"
    }
}

struct RemoteListing: Decodable {
    let id: String?
    let title: String
    let address: String?
    let neighborhood: String?
    let borough: String?
    let latitude: Double?
    let longitude: Double?
    let sizeSqft: Int?
    let priceMonthly: Double?
    let photos: [String]
    let amenities: [String]
    let description: String?
    let leaseTerms: RemoteLeaseTerms?
    let useType: String?

    enum CodingKeys: String, CodingKey {
        case id, title, address, neighborhood, borough, latitude, longitude
        case sizeSqft = "size_sqft"
        case priceMonthly = "price_monthly"
        case photos, amenities, description
        case leaseTerms = "lease_terms"
        case useType = "use_type"
    }

    func toStudioListing() -> StudioListing {
        // Build display address — combine title + street address when available
        let boroughWords: Set<String> = ["manhattan", "brooklyn", "queens", "bronx", "staten island"]
        let displayAddress: String
        if let addr = address, !addr.isEmpty, !boroughWords.contains(addr.lowercased()) {
            displayAddress = "\(title) · \(addr)"
        } else {
            displayAddress = title
        }

        // Parse available date or default to 30 days out
        var availableDate = Calendar.current.date(byAdding: .day, value: 30, to: Date()) ?? Date()
        if let dateStr = leaseTerms?.availableDate {
            let fmt = ISO8601DateFormatter()
            fmt.formatOptions = [.withFullDate]
            availableDate = fmt.date(from: dateStr) ?? availableDate
        }

        // Coordinate fallback keyed on neighborhood/borough
        let (lat, lon) = resolvedCoordinates()

        return StudioListing(
            id: UUID(),
            address: displayAddress,
            neighborhood: neighborhood ?? borough?.capitalized ?? "New York",
            sqft: sizeSqft ?? 0,
            monthlyRent: Int(priceMonthly ?? 0),
            photos: photos,
            amenities: amenities,
            leaseTermMonths: leaseTerms?.minMonths ?? 12,
            availableDate: availableDate,
            coTenantCompatibilityScore: nil,
            latitude: lat,
            longitude: lon
        )
    }

    // Default coordinates per neighborhood / building address
    private func resolvedCoordinates() -> (Double, Double) {
        if let latitude, let longitude { return (latitude, longitude) }
        // Known Rockella building addresses
        if let addr = address {
            if addr.contains("1660 E New York Ave") { return (40.6579, -73.9052) }
            if addr.contains("1639 Centre St")      { return (40.7037, -73.9131) }
            if addr.contains("520 8th Ave")         { return (40.7527, -73.9967) }
        }
        // Borough / neighborhood fallbacks
        let lookup: [String: (Double, Double)] = [
            "brooklyn":   (40.6782, -73.9442),
            "manhattan":  (40.7527, -73.9967),
            "queens":     (40.7282, -73.7949),
            "bronx":      (40.8448, -73.8648),
            "bushwick":   (40.7054, -73.9217),
            "williamsburg": (40.7140, -73.9642),
            "long island city": (40.7440, -73.9484),
            "gowanus":    (40.6745, -73.9893),
            "harlem":     (40.8118, -73.9488),
            "astoria":    (40.7554, -73.9302),
            "ridgewood":  (40.7040, -73.9129),
        ]
        let key = (neighborhood ?? borough ?? "").lowercased()
        return lookup[key] ?? (40.7282, -73.9542)  // NYC centre
    }
}
