import SwiftUI
import MapKit

struct MatchResultsView: View {
    @EnvironmentObject var appState: AppState

    @State private var selectedSegment: Int = 0
    @State private var selectedListing: StudioListing?
    @State private var searchText: String = ""
    @State private var showingFilters: Bool = false
    @State private var mapPosition: MapCameraPosition = .region(
        MKCoordinateRegion(
            center: CLLocationCoordinate2D(latitude: 40.7282, longitude: -73.9542),
            span: MKCoordinateSpan(latitudeDelta: 0.18, longitudeDelta: 0.18)
        )
    )

    private let background = Color(red: 0.97, green: 0.96, blue: 0.94)
    private let accent = Color(red: 0.18, green: 0.16, blue: 0.14)

    private var listings: [StudioListing] {
        guard !searchText.isEmpty else { return appState.filteredListings() }
        // Search scans all listings regardless of filter criteria so an explicit
        // address or neighborhood query always returns results.
        let q = searchText.lowercased()
        return appState.listings.filter {
            $0.address.lowercased().contains(q) ||
            $0.neighborhood.lowercased().contains(q)
        }
    }

    var body: some View {
        ZStack {
            background.ignoresSafeArea()

            VStack(spacing: 0) {
                segmentControl
                    .padding(.horizontal, 20)
                    .padding(.top, 8)
                    .padding(.bottom, 12)

                if appState.isLoadingListings {
                    loadingView
                } else if let error = appState.apiError, appState.listings.isEmpty {
                    errorView(error)
                } else if selectedSegment == 0 {
                    listView
                } else {
                    mapView
                }
            }
        }
        .navigationTitle(appState.isLoadingListings ? "Loading…" : (listings.isEmpty ? "No Matches" : "\(listings.count) Space\(listings.count == 1 ? "" : "s") Found"))
        .navigationBarTitleDisplayMode(.large)
        .searchable(text: $searchText, placement: .navigationBarDrawer(displayMode: .always), prompt: "Search by address or neighborhood")
        .toolbar {
            ToolbarItem(placement: .topBarLeading) {
                dataSourceBadge
            }
            ToolbarItem(placement: .topBarTrailing) {
                HStack(spacing: 4) {
                    Button {
                        Task { await appState.refreshListings() }
                    } label: {
                        Image(systemName: "arrow.clockwise")
                            .foregroundStyle(accent)
                    }
                    if appState.needs != nil {
                        Button {
                            appState.clearNeeds()
                        } label: {
                            Text("Clear")
                                .font(.subheadline)
                                .foregroundStyle(accent)
                        }
                    }
                    Button {
                        showingFilters = true
                    } label: {
                        Label("Edit Filters", systemImage: "slider.horizontal.3")
                            .foregroundStyle(accent)
                    }
                }
            }
        }
        .sheet(isPresented: $showingFilters) {
            NeedsFormView(isSheet: true)
                .environmentObject(appState)
        }
        .task {
            await appState.loadListings()
        }
    }

    // MARK: - Loading

    private var loadingView: some View {
        VStack(spacing: 16) {
            Spacer()
            ProgressView()
                .scaleEffect(1.4)
                .tint(accent)
            Text("Fetching listings…")
                .font(.subheadline)
                .foregroundStyle(.secondary)
            Spacer()
        }
    }

    private var dataSourceBadge: some View {
        HStack(spacing: 4) {
            Circle()
                .fill(appState.isLiveData ? Color.green : Color.orange)
                .frame(width: 7, height: 7)
            Text(appState.isLiveData ? "Live" : "Cached")
                .font(.caption2)
                .fontWeight(.medium)
                .foregroundStyle(.secondary)
        }
    }

    // MARK: - Segment Control
    private var segmentControl: some View {
        HStack(spacing: 0) {
            segmentButton(title: "List", icon: "list.bullet", index: 0)
            segmentButton(title: "Map", icon: "map", index: 1)
        }
        .padding(4)
        .background(accent.opacity(0.08))
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }

    private func segmentButton(title: String, icon: String, index: Int) -> some View {
        Button {
            withAnimation(.spring(response: 0.3)) {
                selectedSegment = index
            }
        } label: {
            HStack(spacing: 6) {
                Image(systemName: icon)
                    .font(.system(size: 12, weight: .medium))
                Text(title)
                    .font(.subheadline)
                    .fontWeight(.medium)
            }
            .foregroundStyle(selectedSegment == index ? accent : accent.opacity(0.45))
            .frame(maxWidth: .infinity)
            .padding(.vertical, 10)
            .background(
                selectedSegment == index
                ? Color.white.clipShape(RoundedRectangle(cornerRadius: 8))
                    .shadow(color: .black.opacity(0.07), radius: 4, y: 1)
                : nil
            )
        }
    }

    // MARK: - List View
    private var listView: some View {
        Group {
            if listings.isEmpty {
                emptyState
            } else {
                ScrollView {
                    LazyVStack(spacing: 16) {
                        ForEach(listings) { listing in
                            NavigationLink(destination: SpaceDetailView(listing: listing).environmentObject(appState)) {
                                ListingCardView(listing: listing)
                            }
                            .buttonStyle(.plain)
                        }
                    }
                    .padding(.horizontal, 20)
                    .padding(.vertical, 16)
                }
                .refreshable {
                    await appState.refreshListings()
                }
            }
        }
    }

    // MARK: - Map View
    private var mapView: some View {
        ZStack(alignment: .bottom) {
            Map(position: $mapPosition) {
                ForEach(listings.filter { $0.latitude != 0 && $0.longitude != 0 }) { listing in
                    Annotation(listing.neighborhood, coordinate: CLLocationCoordinate2D(
                        latitude: listing.latitude,
                        longitude: listing.longitude
                    )) {
                        Button {
                            withAnimation {
                                selectedListing = listing
                            }
                        } label: {
                            VStack(spacing: 4) {
                                ZStack {
                                    Circle()
                                        .fill(selectedListing?.id == listing.id ? accent : Color.white)
                                        .frame(width: 36, height: 36)
                                        .shadow(color: .black.opacity(0.15), radius: 6, y: 2)

                                    Text(mapPinLabel(listing))
                                        .font(.system(size: 9, weight: .bold))
                                        .foregroundStyle(selectedListing?.id == listing.id ? Color.white : accent)
                                }

                                Image(systemName: "triangle.fill")
                                    .font(.system(size: 6))
                                    .foregroundStyle(selectedListing?.id == listing.id ? accent : Color.white)
                                    .rotationEffect(.degrees(180))
                                    .offset(y: -4)
                            }
                        }
                    }
                }
            }
            .mapStyle(.standard(elevation: .flat))

            if let listing = selectedListing {
                mapCard(listing: listing)
                    .padding(.horizontal, 20)
                    .padding(.bottom, 24)
                    .transition(.move(edge: .bottom).combined(with: .opacity))
            }
        }
    }

    private func mapCard(listing: StudioListing) -> some View {
        NavigationLink(destination: SpaceDetailView(listing: listing).environmentObject(appState)) {
            HStack(spacing: 14) {
                ZStack {
                    RoundedRectangle(cornerRadius: 8)
                        .fill(accent.opacity(0.08))
                        .frame(width: 56, height: 56)
                    Image(systemName: "photo.on.rectangle")
                        .font(.system(size: 20))
                        .foregroundStyle(accent.opacity(0.3))
                }

                VStack(alignment: .leading, spacing: 4) {
                    Text(listing.neighborhood)
                        .font(.caption)
                        .fontWeight(.medium)
                        .foregroundStyle(.secondary)
                        .textCase(.uppercase)
                        .tracking(0.6)
                    Text(listing.address)
                        .font(.subheadline)
                        .fontWeight(.semibold)
                        .foregroundStyle(accent)
                        .lineLimit(1)
                    Text(listingSubtitle(listing))
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                Spacer()

                Image(systemName: "chevron.right")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(accent.opacity(0.4))
            }
            .padding(14)
            .background(Color.white)
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .shadow(color: .black.opacity(0.1), radius: 12, y: 4)
        }
        .buttonStyle(.plain)
    }

    private func mapPinLabel(_ listing: StudioListing) -> String {
        guard listing.monthlyRent > 0 else { return "●" }
        if listing.monthlyRent >= 1000 {
            let k = Double(listing.monthlyRent) / 1000.0
            return k.truncatingRemainder(dividingBy: 1) == 0
                ? "$\(Int(k))k"
                : String(format: "$%.1fk", k)
        }
        return "$\(listing.monthlyRent)"
    }

    private func listingSubtitle(_ listing: StudioListing) -> String {
        var parts: [String] = []
        if listing.sqft > 0 { parts.append("\(listing.sqft) sq ft") }
        if listing.monthlyRent > 0 { parts.append("$\(listing.monthlyRent)/mo") }
        return parts.isEmpty ? "Contact for details" : parts.joined(separator: " · ")
    }

    // MARK: - Error State
    private func errorView(_ message: String) -> some View {
        VStack(spacing: 16) {
            Spacer()
            Image(systemName: "wifi.exclamationmark")
                .font(.system(size: 48))
                .foregroundStyle(accent.opacity(0.25))
            Text("Unable to Load Listings")
                .font(.title3)
                .fontWeight(.semibold)
                .foregroundStyle(accent)
            Text(message)
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 40)
            Button {
                Task { await appState.refreshListings() }
            } label: {
                Label("Try Again", systemImage: "arrow.clockwise")
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .foregroundStyle(.white)
                    .padding(.horizontal, 24)
                    .padding(.vertical, 12)
                    .background(accent)
                    .clipShape(Capsule())
            }
            .padding(.top, 8)
            Spacer()
        }
    }

    // MARK: - Empty State
    private var emptyState: some View {
        VStack(spacing: 16) {
            Spacer()
            Image(systemName: "location.slash")
                .font(.system(size: 48))
                .foregroundStyle(accent.opacity(0.2))
            Text("No spaces match your criteria")
                .font(.title3)
                .fontWeight(.semibold)
                .foregroundStyle(accent)
            Text("Try adjusting your budget, square footage, or neighborhood preferences.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 40)
            Spacer()
        }
    }
}

#Preview {
    NavigationStack {
        MatchResultsView()
            .environmentObject(AppState())
    }
}
