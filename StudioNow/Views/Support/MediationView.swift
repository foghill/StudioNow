import SwiftUI

struct MediationView: View {
    @EnvironmentObject var appState: AppState

    @State private var showScheduleSheet: Bool = false
    @State private var newTopic: String = ""
    @State private var newDate: Date = Date()

    private let background = Color(red: 0.97, green: 0.96, blue: 0.94)
    private let accent = Color(red: 0.18, green: 0.16, blue: 0.14)

    private var dateFormatter: DateFormatter {
        let df = DateFormatter()
        df.dateStyle = .long
        df.timeStyle = .short
        return df
    }

    var body: some View {
        ZStack {
            background.ignoresSafeArea()

            ScrollView {
                VStack(spacing: 24) {
                    sessionsSection
                    resourceHubSection
                }
                .padding(.horizontal, 20)
                .padding(.vertical, 24)
            }
        }
        .navigationTitle("Mediation & Support")
        .navigationBarTitleDisplayMode(.large)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button {
                    showScheduleSheet = true
                } label: {
                    HStack(spacing: 5) {
                        Image(systemName: "plus")
                            .font(.system(size: 12, weight: .semibold))
                        Text("Schedule")
                            .font(.subheadline)
                            .fontWeight(.medium)
                    }
                    .foregroundStyle(accent)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 6)
                    .background(accent.opacity(0.08))
                    .clipShape(Capsule())
                }
            }
        }
        .sheet(isPresented: $showScheduleSheet) {
            scheduleSheet
        }
    }

    // MARK: - Sessions Section
    private var sessionsSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Upcoming Sessions")
                .font(.headline)
                .foregroundStyle(accent)

            if appState.mediationSessions.isEmpty {
                VStack(spacing: 12) {
                    Image(systemName: "person.2")
                        .font(.system(size: 36))
                        .foregroundStyle(accent.opacity(0.2))
                    Text("No upcoming sessions")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                    Text("Schedule a free mediation session with your WORTHLESSSTUDIOS coordinator.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                }
                .frame(maxWidth: .infinity)
                .padding(32)
                .background(Color.white)
                .clipShape(RoundedRectangle(cornerRadius: 12))
                .shadow(color: .black.opacity(0.06), radius: 8, y: 2)
            } else {
                VStack(spacing: 12) {
                    ForEach(appState.mediationSessions) { session in
                        sessionCard(session)
                    }
                }
            }
        }
    }

    private func sessionCard(_ session: MediationSession) -> some View {
        HStack(spacing: 16) {
            VStack(spacing: 4) {
                Text(dayString(from: session.date))
                    .font(.system(size: 22, weight: .bold))
                    .foregroundStyle(accent)
                Text(monthString(from: session.date))
                    .font(.caption)
                    .fontWeight(.medium)
                    .foregroundStyle(accent.opacity(0.5))
                    .textCase(.uppercase)
                    .tracking(0.6)
            }
            .frame(width: 48)

            Rectangle()
                .fill(accent.opacity(0.1))
                .frame(width: 1, height: 44)

            VStack(alignment: .leading, spacing: 4) {
                Text(session.topic)
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .foregroundStyle(accent)

                Text(session.status)
                    .font(.caption)
                    .fontWeight(.semibold)
                    .foregroundStyle(session.status == "Scheduled" ? .green : .orange)
            }

            Spacer()

            Image(systemName: "video.circle.fill")
                .font(.system(size: 28))
                .foregroundStyle(accent.opacity(0.15))
        }
        .padding(16)
        .background(Color.white)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .shadow(color: .black.opacity(0.06), radius: 8, y: 2)
    }

    // MARK: - Resource Hub
    private var resourceHubSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Resource Hub")
                .font(.headline)
                .foregroundStyle(accent)

            VStack(spacing: 12) {
                ForEach(hubResources, id: \.title) { resource in
                    resourceCard(resource)
                }
            }
        }
        .padding(.bottom, 8)
    }

    private func resourceCard(_ resource: (title: String, description: String, icon: String)) -> some View {
        HStack(spacing: 16) {
            ZStack {
                RoundedRectangle(cornerRadius: 10)
                    .fill(accent.opacity(0.07))
                    .frame(width: 44, height: 44)
                Image(systemName: resource.icon)
                    .font(.system(size: 18))
                    .foregroundStyle(accent.opacity(0.55))
            }

            VStack(alignment: .leading, spacing: 4) {
                Text(resource.title)
                    .font(.subheadline)
                    .fontWeight(.semibold)
                    .foregroundStyle(accent)
                Text(resource.description)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
                    .fixedSize(horizontal: false, vertical: true)
            }

            Spacer()
        }
        .padding(16)
        .background(Color.white)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .shadow(color: .black.opacity(0.06), radius: 8, y: 2)
    }

    // MARK: - Schedule Sheet
    private var scheduleSheet: some View {
        NavigationStack {
            ZStack {
                background.ignoresSafeArea()

                VStack(spacing: 24) {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("What would you like to discuss?")
                            .font(.caption)
                            .fontWeight(.medium)
                            .foregroundStyle(accent.opacity(0.6))
                            .textCase(.uppercase)
                            .tracking(1)

                        TextField("e.g. Studio hours, shared supplies...", text: $newTopic, axis: .vertical)
                            .lineLimit(3...5)
                            .font(.body)
                            .padding(14)
                            .background(Color.white)
                            .clipShape(RoundedRectangle(cornerRadius: 12))
                            .shadow(color: .black.opacity(0.06), radius: 8, y: 2)
                    }

                    VStack(alignment: .leading, spacing: 8) {
                        Text("Preferred Date & Time")
                            .font(.caption)
                            .fontWeight(.medium)
                            .foregroundStyle(accent.opacity(0.6))
                            .textCase(.uppercase)
                            .tracking(1)

                        DatePicker("", selection: $newDate, in: Date()..., displayedComponents: [.date, .hourAndMinute])
                            .labelsHidden()
                            .padding(14)
                            .background(Color.white)
                            .clipShape(RoundedRectangle(cornerRadius: 12))
                            .shadow(color: .black.opacity(0.06), radius: 8, y: 2)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }

                    Spacer()

                    Button {
                        let session = MediationSession(
                            date: newDate,
                            topic: newTopic.trimmingCharacters(in: .whitespaces),
                            status: "Pending Confirmation"
                        )
                        appState.mediationSessions.append(session)
                        newTopic = ""
                        newDate = Date()
                        showScheduleSheet = false
                    } label: {
                        Text("Request Session")
                            .font(.headline)
                            .foregroundStyle(background)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 18)
                            .background(newTopic.trimmingCharacters(in: .whitespaces).isEmpty ? accent.opacity(0.3) : accent)
                            .clipShape(RoundedRectangle(cornerRadius: 12))
                    }
                    .disabled(newTopic.trimmingCharacters(in: .whitespaces).isEmpty)
                }
                .padding(20)
            }
            .navigationTitle("Schedule Mediation")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Cancel") {
                        showScheduleSheet = false
                    }
                    .foregroundStyle(accent.opacity(0.6))
                }
            }
        }
    }

    // MARK: - Helpers
    private func dayString(from date: Date) -> String {
        let df = DateFormatter()
        df.dateFormat = "d"
        return df.string(from: date)
    }

    private func monthString(from date: Date) -> String {
        let df = DateFormatter()
        df.dateFormat = "MMM"
        return df.string(from: date)
    }

    private var hubResources: [(title: String, description: String, icon: String)] {
        [
            (
                title: "Studio Setup Tips",
                description: "Best practices for organizing your studio, managing materials, and creating a productive workspace.",
                icon: "paintbrush.pointed"
            ),
            (
                title: "Tenant Rights in NYC",
                description: "Know your legal rights as a commercial tenant, including protections against harassment and illegal eviction.",
                icon: "shield.lefthalf.filled"
            ),
            (
                title: "Co-Tenant Guidelines",
                description: "Community standards for shared studio spaces — noise, schedules, shared supplies, and conflict resolution.",
                icon: "person.2"
            ),
            (
                title: "Community Forums",
                description: "Connect with other WORTHLESSSTUDIOS artists, share resources, and find collaborators.",
                icon: "bubble.left.and.bubble.right"
            ),
            (
                title: "Emergency Assistance",
                description: "If you're facing immediate housing or studio loss, our team can connect you to rapid-response resources.",
                icon: "exclamationmark.triangle"
            )
        ]
    }
}

#Preview {
    NavigationStack {
        MediationView()
            .environmentObject(AppState())
    }
}
