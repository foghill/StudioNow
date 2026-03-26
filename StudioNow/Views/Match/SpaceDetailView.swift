import SwiftUI

struct SpaceDetailView: View {
    let listing: StudioListing
    @EnvironmentObject var appState: AppState
    @Environment(\.dismiss) private var dismiss

    @State private var showConfirmation: Bool = false

    private let background = Color(red: 0.97, green: 0.96, blue: 0.94)
    private let accent = Color(red: 0.18, green: 0.16, blue: 0.14)

    private var dateFormatter: DateFormatter {
        let df = DateFormatter()
        df.dateStyle = .medium
        return df
    }

    var body: some View {
        ZStack(alignment: .bottom) {
            background.ignoresSafeArea()

            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    photoArea
                    contentArea
                    Color.clear.frame(height: 100)
                }
            }
            .ignoresSafeArea(edges: .top)

            ctaButton
        }
        .navigationBarTitleDisplayMode(.inline)
        .alert("Request Submitted", isPresented: $showConfirmation) {
            Button("Great!", role: .cancel) { dismiss() }
        } message: {
            Text("Your request for \(listing.address) has been submitted. We'll be in touch soon.")
        }
    }

    // MARK: - Photo Area
    private var photoArea: some View {
        Group {
            if let photo = listing.photos.first, photo.hasPrefix("http"),
               let url = URL(string: photo) {
                AsyncImage(url: url) { phase in
                    switch phase {
                    case .success(let image):
                        image.resizable().aspectRatio(contentMode: .fill)
                    default:
                        photoPlaceholder
                    }
                }
            } else {
                photoPlaceholder
            }
        }
        .frame(height: 280)
        .clipped()
    }

    private var photoPlaceholder: some View {
        ZStack {
            LinearGradient(
                colors: [accent.opacity(0.18), accent.opacity(0.08)],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            VStack(spacing: 12) {
                Image(systemName: "photo.on.rectangle")
                    .font(.system(size: 48))
                    .foregroundStyle(accent.opacity(0.3))
                Text("No photos available")
                    .font(.caption)
                    .foregroundStyle(accent.opacity(0.4))
            }
        }
    }

    // MARK: - Content
    private var contentArea: some View {
        VStack(alignment: .leading, spacing: 24) {
            // Header
            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(listing.neighborhood)
                            .font(.caption)
                            .fontWeight(.medium)
                            .foregroundStyle(accent.opacity(0.5))
                            .textCase(.uppercase)
                            .tracking(0.8)

                        Text(listing.address)
                            .font(.title2)
                            .fontWeight(.bold)
                            .foregroundStyle(accent)
                    }
                    Spacer()
                    saveButton
                }

                if let score = listing.coTenantCompatibilityScore {
                    let pct = Int(score * 100)
                    let color: Color = score >= 0.8 ? .green : score >= 0.6 ? .orange : .red
                    Text("\(pct)% co-tenant match")
                        .font(.caption)
                        .fontWeight(.semibold)
                        .foregroundStyle(.white)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 5)
                        .background(color)
                        .clipShape(Capsule())
                }
            }

            // Stats Row
            HStack(spacing: 0) {
                statItem(value: "\(listing.sqft)", unit: "sq ft", icon: "square.dashed")
                Divider().frame(height: 40)
                statItem(value: "$\(listing.monthlyRent)", unit: "per month", icon: "dollarsign.circle")
                Divider().frame(height: 40)
                statItem(value: "\(listing.leaseTermMonths)", unit: "mo lease", icon: "calendar")
            }
            .padding(16)
            .background(Color.white)
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .shadow(color: .black.opacity(0.06), radius: 8, y: 2)

            // Available Date
            HStack(spacing: 10) {
                Image(systemName: "calendar.badge.checkmark")
                    .font(.system(size: 16))
                    .foregroundStyle(accent.opacity(0.6))
                VStack(alignment: .leading, spacing: 2) {
                    Text("Available")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Text(dateFormatter.string(from: listing.availableDate))
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .foregroundStyle(accent)
                }
            }
            .padding(14)
            .background(Color.white)
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .shadow(color: .black.opacity(0.06), radius: 8, y: 2)

            // Amenities
            VStack(alignment: .leading, spacing: 12) {
                Text("Amenities")
                    .font(.headline)
                    .foregroundStyle(accent)

                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(listing.amenities, id: \.self) { amenity in
                            Text(amenity)
                                .font(.subheadline)
                                .foregroundStyle(accent)
                                .padding(.horizontal, 14)
                                .padding(.vertical, 8)
                                .background(Color.white)
                                .clipShape(Capsule())
                                .shadow(color: .black.opacity(0.06), radius: 4, y: 1)
                        }
                    }
                    .padding(.horizontal, 1)
                    .padding(.vertical, 4)
                }
            }

            // Co-tenant Section
            if let score = listing.coTenantCompatibilityScore {
                coTenantSection(score: score)
            }
        }
        .padding(20)
    }

    private func statItem(value: String, unit: String, icon: String) -> some View {
        VStack(spacing: 4) {
            Image(systemName: icon)
                .font(.system(size: 16))
                .foregroundStyle(accent.opacity(0.5))
            Text(value)
                .font(.headline)
                .fontWeight(.bold)
                .foregroundStyle(accent)
            Text(unit)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
    }

    private func coTenantSection(score: Double) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Co-Tenant Compatibility")
                .font(.headline)
                .foregroundStyle(accent)

            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text("Compatibility Score")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                    Spacer()
                    Text("\(Int(score * 100))%")
                        .font(.subheadline)
                        .fontWeight(.semibold)
                        .foregroundStyle(accent)
                }

                ProgressView(value: score)
                    .tint(score >= 0.8 ? .green : score >= 0.6 ? .orange : .red)
                    .scaleEffect(x: 1, y: 1.5)

                Text("This space is compatible with other artists in similar disciplines and schedules.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .padding(.top, 4)
            }
            .padding(16)
            .background(Color.white)
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .shadow(color: .black.opacity(0.06), radius: 8, y: 2)
        }
    }

    private var saveButton: some View {
        Button {
            appState.toggleSaved(listing.id)
        } label: {
            Image(systemName: appState.savedListingIDs.contains(listing.id) ? "heart.fill" : "heart")
                .font(.system(size: 20))
                .foregroundStyle(appState.savedListingIDs.contains(listing.id) ? .red : accent.opacity(0.4))
        }
    }

    private var ctaButton: some View {
        VStack(spacing: 0) {
            Divider()
            Button {
                appState.applicationStatus = .submitted
                showConfirmation = true
            } label: {
                HStack(spacing: 10) {
                    if appState.applicationStatus == .submitted || appState.applicationStatus == .underReview || appState.applicationStatus == .approved || appState.applicationStatus == .active {
                        Image(systemName: "checkmark.circle.fill")
                    }
                    Text(appState.applicationStatus == .notStarted ? "Request This Space" : "Application \(appState.applicationStatus.rawValue)")
                        .font(.headline)
                }
                .foregroundStyle(Color(red: 0.97, green: 0.96, blue: 0.94))
                .frame(maxWidth: .infinity)
                .padding(.vertical, 18)
                .background(accent)
                .clipShape(RoundedRectangle(cornerRadius: 12))
            }
            .disabled(appState.applicationStatus != .notStarted)
            .padding(.horizontal, 20)
            .padding(.vertical, 16)
            .background(Color(red: 0.97, green: 0.96, blue: 0.94))
        }
    }
}

#Preview {
    NavigationStack {
        SpaceDetailView(listing: MockData.listings[0])
            .environmentObject(AppState())
    }
}
