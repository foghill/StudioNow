import Foundation
import Observation

@MainActor
final class AppState: ObservableObject {
    @Published var profile: ArtistProfile?
    @Published var needs: StudioNeeds?
    @Published var applicationStatus: ApplicationStatus = .notStarted
    @Published var mediationSessions: [MediationSession] = MockData.mediationSessions
    @Published var savedListingIDs: Set<UUID> = []

    /// All available listings — populated from the API; falls back to MockData.
    @Published var listings: [StudioListing] = MockData.listings
    @Published var isLoadingListings = false
    @Published var isLiveData = false   // true when listings came from the API

    private let needsKey = "savedStudioNeeds"
    private let apiURL = URL(string: "http://127.0.0.1:8000/listings?limit=200")!

    init() {
        loadNeeds()
    }

    // MARK: - API

    func loadListings() async {
        guard !isLiveData else { return }  // already fetched this session
        isLoadingListings = true
        defer { isLoadingListings = false }

        do {
            let (data, response) = try await URLSession.shared.data(from: apiURL)
            guard (response as? HTTPURLResponse)?.statusCode == 200 else { return }

            let decoded = try JSONDecoder().decode(APIListingsResponse.self, from: data)
            let mapped = decoded.listings.map { $0.toStudioListing() }

            if !mapped.isEmpty {
                listings = mapped
                isLiveData = true
            }
        } catch {
            // API unreachable — keep using MockData.listings (already set)
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
            let sqftOk = listing.sqft >= needs.minSqft && listing.sqft <= needs.maxSqft
            let budgetOk = listing.monthlyRent <= needs.maxMonthlyBudget
            let neighborhoodOk = needs.neighborhoods.isEmpty || neighborhoodMatches(listing.neighborhood, selected: needs.neighborhoods)
            let coTenantOk = !needs.openToCoTenants || listing.coTenantCompatibilityScore != nil
            return sqftOk && budgetOk && neighborhoodOk && coTenantOk
        }
    }

    private func neighborhoodMatches(_ listingNeighborhood: String, selected: [String]) -> Bool {
        if selected.contains(listingNeighborhood) { return true }
        for borough in selected {
            if let subs = MockData.boroughNeighborhoods[borough], subs.contains(listingNeighborhood) {
                return true
            }
        }
        return false
    }
}