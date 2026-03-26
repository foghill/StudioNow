import Foundation
import Observation

@MainActor
final class AppState: ObservableObject {
    @Published var profile: ArtistProfile?
    @Published var needs: StudioNeeds?
    @Published var applicationStatus: ApplicationStatus = .notStarted
    @Published var mediationSessions: [MediationSession] = MockData.mediationSessions
    @Published var savedListingIDs: Set<UUID> = []

    /// All available listings — populated exclusively from the API.
    @Published var listings: [StudioListing] = []
    @Published var isLoadingListings = false
    @Published var isLiveData = false
    @Published var apiError: String?

    private let needsKey = "savedStudioNeeds"
    private let apiURL = URL(string: "http://127.0.0.1:8000/listings?limit=2000")!

    init() {
        loadNeeds()
    }

    // MARK: - API

    func loadListings() async {
        guard !isLiveData else { return }  // already fetched this session
        isLoadingListings = true
        apiError = nil
        defer { isLoadingListings = false }

        do {
            let (data, response) = try await URLSession.shared.data(from: apiURL)
            guard let httpResponse = response as? HTTPURLResponse else {
                apiError = "Invalid response from server"
                return
            }
            guard httpResponse.statusCode == 200 else {
                apiError = "Server returned \(httpResponse.statusCode)"
                return
            }

            let decoded = try JSONDecoder().decode(APIListingsResponse.self, from: data)
            let mapped = decoded.listings.map { $0.toStudioListing() }

            listings = mapped
            isLiveData = true
            apiError = nil
        } catch let error as URLError where error.code == .cannotConnectToHost || error.code == .timedOut {
            apiError = "Cannot connect to server. Make sure the API is running on localhost:8000."
        } catch {
            apiError = "Failed to load listings: \(error.localizedDescription)"
        }
    }

    /// Force a fresh fetch from the API, bypassing the session cache.
    /// Use this when the user explicitly requests up-to-date listings.
    func refreshListings() async {
        isLiveData = false
        await loadListings()
    }

    // MARK: - Profile / needs

    func saveProfile(_ profile: ArtistProfile) {
        self.profile = profile
    }

    func saveNeeds(_ needs: StudioNeeds) {
        self.needs = needs
        if let data = try? JSONEncoder().encode(needs) {
            UserDefaults.standard.set(data, forKey: needsKey)
        }
    }

    func clearNeeds() {
        self.needs = nil
        UserDefaults.standard.removeObject(forKey: needsKey)
    }

    private func loadNeeds() {
        guard let data = UserDefaults.standard.data(forKey: needsKey),
              let saved = try? JSONDecoder().decode(StudioNeeds.self, from: data) else { return }
        self.needs = saved
    }

    // MARK: - Saved listings

    func toggleSaved(_ listingID: UUID) {
        if savedListingIDs.contains(listingID) {
            savedListingIDs.remove(listingID)
        } else {
            savedListingIDs.insert(listingID)
        }
    }

    // MARK: - Filtering

    func filteredListings() -> [StudioListing] {
        guard let needs else { return listings }
        return listings.filter { listing in
            // Treat 0 as "unknown" — don't filter out listings missing data
            let sqftOk = listing.sqft == 0 || (listing.sqft >= needs.minSqft && listing.sqft <= needs.maxSqft)
            let budgetOk = listing.monthlyRent == 0 || listing.monthlyRent <= needs.maxMonthlyBudget
            let neighborhoodOk = needs.neighborhoods.isEmpty || neighborhoodMatches(listing.neighborhood, selected: needs.neighborhoods)
            let coTenantOk = !needs.openToCoTenants || listing.coTenantCompatibilityScore != nil
            return sqftOk && budgetOk && neighborhoodOk && coTenantOk
        }
    }

    private func neighborhoodMatches(_ listingNeighborhood: String, selected: [String]) -> Bool {
        // Direct match (e.g. listing says "Chelsea", user selected "Chelsea")
        if selected.contains(listingNeighborhood) { return true }

        // Case-insensitive match
        let lower = listingNeighborhood.lowercased()
        if selected.contains(where: { $0.lowercased() == lower }) { return true }

        // Borough selected → match all neighborhoods in that borough
        // (e.g. user selected "Chelsea" which is in Manhattan → listing says "Manhattan")
        for selectedName in selected {
            // Check if selectedName is a borough containing this listing's neighborhood
            if let subs = MockData.boroughNeighborhoods[selectedName], subs.contains(listingNeighborhood) {
                return true
            }
        }

        // Listing has a borough-level value like "New York" or "Brooklyn" —
        // resolve it to a borough, then check if any selected neighborhood is in that borough
        if let resolvedBorough = MockData.neighborhoodToBoroughFallback[listingNeighborhood] {
            // Check if user selected this borough directly
            if selected.contains(resolvedBorough) { return true }
            // Check if user selected ANY neighborhood within this borough
            if let subs = MockData.boroughNeighborhoods[resolvedBorough] {
                for selectedName in selected {
                    if subs.contains(selectedName) { return true }
                }
            }
        }

        return false
    }
}