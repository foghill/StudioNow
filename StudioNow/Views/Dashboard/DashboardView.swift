import SwiftUI

struct DashboardView: View {
    @EnvironmentObject var appState: AppState

    private let background = Color(red: 0.97, green: 0.96, blue: 0.94)
    private let accent = Color(red: 0.18, green: 0.16, blue: 0.14)

    private var dateFormatter: DateFormatter {
        let df = DateFormatter()
        df.dateStyle = .medium
        return df
    }

    var body: some View {
        ZStack {
            background.ignoresSafeArea()

            ScrollView {
                VStack(spacing: 24) {
                    applicationStatusCard
                    rentScheduleCard
                    mediationsCard
                    resourcesCard
                }
                .padding(.horizontal, 20)
                .padding(.vertical, 24)
            }
        }
        .navigationTitle("Dashboard")
        .navigationBarTitleDisplayMode(.large)
    }

    // MARK: - Application Status Card
    private var applicationStatusCard: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Application Status")
                .font(.headline)
                .foregroundStyle(accent)

            HStack(spacing: 16) {
                ZStack {
                    Circle()
                        .fill(statusColor(appState.applicationStatus).opacity(0.12))
                        .frame(width: 52, height: 52)
                    Image(systemName: appState.applicationStatus.icon)
                        .font(.system(size: 22))
                        .foregroundStyle(statusColor(appState.applicationStatus))
                }

                VStack(alignment: .leading, spacing: 4) {
                    Text(appState.applicationStatus.rawValue)
                        .font(.title3)
                        .fontWeight(.bold)
                        .foregroundStyle(accent)
                    Text(appState.applicationStatus.description)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }

                Spacer()
            }

            // Progress dots
            HStack(spacing: 6) {
                ForEach(ApplicationStatus.allCases, id: \.self) { status in
                    let isReached = statusIndex(status) <= statusIndex(appState.applicationStatus)
                    Capsule()
                        .fill(isReached ? statusColor(appState.applicationStatus) : accent.opacity(0.12))
                        .frame(maxWidth: .infinity)
                        .frame(height: 6)
                }
            }
        }
        .padding(20)
        .background(Color.white)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .shadow(color: .black.opacity(0.06), radius: 8, y: 2)
    }

    // MARK: - Rent Schedule Card
    private var rentScheduleCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Rent Schedule")
                .font(.headline)
                .foregroundStyle(accent)

            HStack(spacing: 14) {
                Image(systemName: "calendar.badge.clock")
                    .font(.system(size: 28))
                    .foregroundStyle(accent.opacity(0.25))

                Text("Your rent schedule will appear here once your application is approved.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .padding(16)
            .background(accent.opacity(0.04))
            .clipShape(RoundedRectangle(cornerRadius: 8))
        }
        .padding(20)
        .background(Color.white)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .shadow(color: .black.opacity(0.06), radius: 8, y: 2)
    }

    // MARK: - Mediations Card
    private var mediationsCard: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Upcoming Mediations")
                .font(.headline)
                .foregroundStyle(accent)

            if appState.mediationSessions.isEmpty {
                Text("No upcoming sessions.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .padding(.vertical, 8)
            } else {
                VStack(spacing: 0) {
                    ForEach(appState.mediationSessions) { session in
                        sessionRow(session)
                        if session.id != appState.mediationSessions.last?.id {
                            Divider().padding(.leading, 56)
                        }
                    }
                }
                .background(accent.opacity(0.03))
                .clipShape(RoundedRectangle(cornerRadius: 8))
            }
        }
        .padding(20)
        .background(Color.white)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .shadow(color: .black.opacity(0.06), radius: 8, y: 2)
    }

    private func sessionRow(_ session: MediationSession) -> some View {
        HStack(spacing: 12) {
            ZStack {
                Circle()
                    .fill(accent.opacity(0.08))
                    .frame(width: 40, height: 40)
                Image(systemName: "person.2.fill")
                    .font(.system(size: 14))
                    .foregroundStyle(accent.opacity(0.5))
            }

            VStack(alignment: .leading, spacing: 3) {
                Text(session.topic)
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .foregroundStyle(accent)
                    .lineLimit(1)

                HStack(spacing: 6) {
                    Text(dateFormatter.string(from: session.date))
                        .font(.caption)
                        .foregroundStyle(.secondary)

                    Text("·")
                        .foregroundStyle(.secondary)

                    Text(session.status)
                        .font(.caption)
                        .fontWeight(.medium)
                        .foregroundStyle(session.status == "Scheduled" ? .green : .orange)
                }
            }

            Spacer()
        }
        .padding(12)
    }

    // MARK: - Resources Card
    private var resourcesCard: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Support Resources")
                .font(.headline)
                .foregroundStyle(accent)

            VStack(spacing: 0) {
                ForEach(resources, id: \.title) { resource in
                    Link(destination: URL(string: resource.url)!) {
                        HStack(spacing: 14) {
                            Image(systemName: resource.icon)
                                .font(.system(size: 16))
                                .foregroundStyle(accent.opacity(0.6))
                                .frame(width: 28)

                            VStack(alignment: .leading, spacing: 2) {
                                Text(resource.title)
                                    .font(.subheadline)
                                    .fontWeight(.medium)
                                    .foregroundStyle(accent)
                                Text(resource.subtitle)
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }

                            Spacer()

                            Image(systemName: "arrow.up.right")
                                .font(.system(size: 11, weight: .medium))
                                .foregroundStyle(accent.opacity(0.3))
                        }
                        .padding(.horizontal, 16)
                        .padding(.vertical, 12)
                    }

                    if resource.title != resources.last?.title {
                        Divider().padding(.leading, 58)
                    }
                }
            }
            .background(accent.opacity(0.03))
            .clipShape(RoundedRectangle(cornerRadius: 8))
        }
        .padding(20)
        .background(Color.white)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .shadow(color: .black.opacity(0.06), radius: 8, y: 2)
        .padding(.bottom, 8)
    }

    // MARK: - Helpers
    private func statusColor(_ status: ApplicationStatus) -> Color {
        switch status {
        case .notStarted: return .gray
        case .submitted: return .blue
        case .underReview: return .orange
        case .approved: return .green
        case .active: return Color(red: 0.18, green: 0.16, blue: 0.14)
        }
    }

    private func statusIndex(_ status: ApplicationStatus) -> Int {
        ApplicationStatus.allCases.firstIndex(of: status) ?? 0
    }

    private var resources: [(title: String, subtitle: String, icon: String, url: String)] {
        [
            (
                title: "NYC Artist Studio Program",
                subtitle: "City-funded affordable studio spaces for NYC artists",
                icon: "building.2",
                url: "https://www.nyc.gov/site/dcla/index.page"
            ),
            (
                title: "Rent Stabilization Info",
                subtitle: "Understand your rights under NYC rent stabilization",
                icon: "doc.text",
                url: "https://www.nyc.gov/site/hpd/services-and-information/rent-stabilization.page"
            ),
            (
                title: "Tenant Rights Guide",
                subtitle: "Know your protections as an NYC commercial tenant",
                icon: "shield.lefthalf.filled",
                url: "https://www.nyc.gov/site/hpd/index.page"
            )
        ]
    }
}

#Preview {
    NavigationStack {
        DashboardView()
            .environmentObject(AppState())
    }
}
