import SwiftUI

struct ListingCardView: View {
    let listing: StudioListing

    private let accent = Color(red: 0.18, green: 0.16, blue: 0.14)

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Photo area — real URL or placeholder
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
            .frame(height: 140)
            .clipped()
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .overlay(alignment: .topTrailing) {
                if let score = listing.coTenantCompatibilityScore {
                    compatibilityBadge(score: score)
                        .padding(10)
                }
            }

            VStack(alignment: .leading, spacing: 8) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(listing.neighborhood)
                        .font(.caption)
                        .fontWeight(.medium)
                        .foregroundStyle(accent.opacity(0.5))
                        .textCase(.uppercase)
                        .tracking(0.8)

                    Text(listing.address)
                        .font(.headline)
                        .foregroundStyle(accent)
                        .lineLimit(1)
                }

                HStack(spacing: 16) {
                    Label("\(listing.sqft) sq ft", systemImage: "square.dashed")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)

                    Spacer()

                    Text("$\(listing.monthlyRent)/mo")
                        .font(.title3)
                        .fontWeight(.bold)
                        .foregroundStyle(accent)
                }

                HStack(spacing: 8) {
                    ForEach(listing.amenities.prefix(3), id: \.self) { amenity in
                        Text(amenity)
                            .font(.caption)
                            .foregroundStyle(accent.opacity(0.7))
                            .padding(.horizontal, 8)
                            .padding(.vertical, 4)
                            .background(accent.opacity(0.07))
                            .clipShape(Capsule())
                    }
                    if listing.amenities.count > 3 {
                        Text("+\(listing.amenities.count - 3)")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            }
            .padding(14)
        }
        .background(Color.white)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .shadow(color: .black.opacity(0.06), radius: 8, y: 2)
    }

    private var photoPlaceholder: some View {
        ZStack {
            LinearGradient(
                colors: [accent.opacity(0.12), accent.opacity(0.06)],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            Image(systemName: "photo.on.rectangle")
                .font(.system(size: 32))
                .foregroundStyle(accent.opacity(0.25))
        }
    }

    private func compatibilityBadge(score: Double) -> some View {
        let percentage = Int(score * 100)
        let color: Color = score >= 0.8 ? .green : score >= 0.6 ? .orange : .red

        return Text("\(percentage)% match")
            .font(.caption)
            .fontWeight(.semibold)
            .foregroundStyle(.white)
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(color)
            .clipShape(Capsule())
    }
}

#Preview {
    ListingCardView(listing: MockData.listings[0])
        .padding()
        .background(Color(red: 0.97, green: 0.96, blue: 0.94))
}
