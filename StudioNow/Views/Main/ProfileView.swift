import SwiftUI

struct ProfileView: View {
    @EnvironmentObject var appState: AppState

    @State private var isEditing: Bool = false
    @State private var editName: String = ""
    @State private var editDiscipline: String = ""
    @State private var editPortfolioURL: String = ""

    private let background = Color(red: 0.97, green: 0.96, blue: 0.94)
    private let accent = Color(red: 0.18, green: 0.16, blue: 0.14)

    var body: some View {
        ZStack {
            background.ignoresSafeArea()

            ScrollView {
                VStack(spacing: 24) {
                    avatarSection
                    infoSection
                    if let needs = appState.needs {
                        needsSummarySection(needs)
                    }
                }
                .padding(.horizontal, 20)
                .padding(.vertical, 24)
            }
        }
        .navigationTitle("Profile")
        .navigationBarTitleDisplayMode(.large)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button(isEditing ? "Done" : "Edit") {
                    if isEditing {
                        if let profile = appState.profile {
                            let updated = ArtistProfile(
                                id: profile.id,
                                name: editName.trimmingCharacters(in: .whitespaces).isEmpty ? profile.name : editName.trimmingCharacters(in: .whitespaces),
                                discipline: editDiscipline.isEmpty ? profile.discipline : editDiscipline,
                                portfolioURL: editPortfolioURL.trimmingCharacters(in: .whitespaces).isEmpty ? nil : editPortfolioURL.trimmingCharacters(in: .whitespaces)
                            )
                            appState.saveProfile(updated)
                        }
                    } else {
                        editName = appState.profile?.name ?? ""
                        editDiscipline = appState.profile?.discipline ?? ""
                        editPortfolioURL = appState.profile?.portfolioURL ?? ""
                    }
                    withAnimation { isEditing.toggle() }
                }
                .fontWeight(.medium)
                .foregroundStyle(accent)
            }
        }
    }

    // MARK: - Avatar
    private var avatarSection: some View {
        VStack(spacing: 16) {
            ZStack {
                Circle()
                    .fill(accent.opacity(0.08))
                    .frame(width: 88, height: 88)

                Text(initials)
                    .font(.system(size: 32, weight: .semibold))
                    .foregroundStyle(accent)
            }

            VStack(spacing: 4) {
                Text(appState.profile?.name ?? "Artist")
                    .font(.title2)
                    .fontWeight(.bold)
                    .foregroundStyle(accent)
                Text(appState.profile?.discipline ?? "")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }

            Text("WORTHLESSSTUDIOS Member")
                .font(.caption)
                .fontWeight(.medium)
                .foregroundStyle(accent.opacity(0.45))
                .padding(.horizontal, 12)
                .padding(.vertical, 5)
                .background(accent.opacity(0.07))
                .clipShape(Capsule())
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 8)
    }

    // MARK: - Info Section
    private var infoSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("About You")
                .font(.headline)
                .foregroundStyle(accent)

            VStack(spacing: 0) {
                if isEditing {
                    editableRow(label: "Name", value: $editName, placeholder: appState.profile?.name ?? "")
                    Divider().padding(.leading, 16)
                    disciplinePickerRow
                    Divider().padding(.leading, 16)
                    editableRow(label: "Portfolio", value: $editPortfolioURL, placeholder: appState.profile?.portfolioURL ?? "https://yourwork.com")
                } else {
                    infoRow(label: "Name", value: appState.profile?.name ?? "—", icon: "person")
                    Divider().padding(.leading, 56)
                    infoRow(label: "Discipline", value: appState.profile?.discipline ?? "—", icon: "paintbrush")
                    if let url = appState.profile?.portfolioURL, !url.isEmpty {
                        Divider().padding(.leading, 56)
                        Link(destination: URL(string: url.hasPrefix("http") ? url : "https://\(url)") ?? URL(string: "https://worthlessstudios.org")!) {
                            infoRow(label: "Portfolio", value: url, icon: "link", isLink: true)
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
            .background(Color.white)
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .shadow(color: .black.opacity(0.06), radius: 8, y: 2)
        }
    }

    private func infoRow(label: String, value: String, icon: String, isLink: Bool = false) -> some View {
        HStack(spacing: 14) {
            Image(systemName: icon)
                .font(.system(size: 15))
                .foregroundStyle(accent.opacity(0.5))
                .frame(width: 28)

            VStack(alignment: .leading, spacing: 2) {
                Text(label)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Text(value)
                    .font(.subheadline)
                    .foregroundStyle(isLink ? .blue : accent)
                    .lineLimit(1)
            }

            Spacer()

            if isLink {
                Image(systemName: "arrow.up.right")
                    .font(.system(size: 11, weight: .medium))
                    .foregroundStyle(.blue.opacity(0.5))
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 14)
    }

    private func editableRow(label: String, value: Binding<String>, placeholder: String) -> some View {
        HStack(spacing: 14) {
            Text(label)
                .font(.subheadline)
                .foregroundStyle(accent.opacity(0.6))
                .frame(width: 70, alignment: .leading)

            TextField(placeholder, text: value)
                .font(.subheadline)
                .foregroundStyle(accent)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 14)
    }

    private var disciplinePickerRow: some View {
        HStack(spacing: 14) {
            Text("Discipline")
                .font(.subheadline)
                .foregroundStyle(accent.opacity(0.6))
                .frame(width: 70, alignment: .leading)

            Picker("Discipline", selection: $editDiscipline) {
                ForEach(MockData.disciplines, id: \.self) { d in
                    Text(d).tag(d)
                }
            }
            .pickerStyle(.menu)
            .tint(accent)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
    }

    // MARK: - Needs Summary
    private func needsSummarySection(_ needs: StudioNeeds) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Your Studio Preferences")
                .font(.headline)
                .foregroundStyle(accent)

            VStack(spacing: 0) {
                summaryRow(label: "Square Footage", value: "\(needs.minSqft)–\(needs.maxSqft) sq ft", icon: "square.dashed")
                Divider().padding(.leading, 56)
                summaryRow(label: "Budget", value: "$\(needs.maxMonthlyBudget)/mo max", icon: "dollarsign.circle")
                Divider().padding(.leading, 56)
                summaryRow(label: "Lease Duration", value: "\(needs.leaseDurationMonths) months", icon: "calendar")
                Divider().padding(.leading, 56)
                summaryRow(label: "Co-Tenants", value: needs.openToCoTenants ? "Open to sharing" : "Solo only", icon: "person.2")
            }
            .background(Color.white)
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .shadow(color: .black.opacity(0.06), radius: 8, y: 2)
        }
        .padding(.bottom, 8)
    }

    private func summaryRow(label: String, value: String, icon: String) -> some View {
        HStack(spacing: 14) {
            Image(systemName: icon)
                .font(.system(size: 15))
                .foregroundStyle(accent.opacity(0.5))
                .frame(width: 28)

            VStack(alignment: .leading, spacing: 2) {
                Text(label)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Text(value)
                    .font(.subheadline)
                    .foregroundStyle(accent)
            }

            Spacer()
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 14)
    }

    // MARK: - Helpers
    private var initials: String {
        guard let name = appState.profile?.name else { return "?" }
        let parts = name.split(separator: " ")
        if parts.count >= 2 {
            return "\(parts[0].prefix(1))\(parts[1].prefix(1))".uppercased()
        }
        return String(name.prefix(2)).uppercased()
    }
}

#Preview {
    NavigationStack {
        ProfileView()
            .environmentObject({
                let state = AppState()
                state.saveProfile(ArtistProfile(name: "Jordan Lee", discipline: "Painting", portfolioURL: "https://jordanlee.art"))
                return state
            }())
    }
}
