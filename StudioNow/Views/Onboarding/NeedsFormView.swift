import SwiftUI

struct NeedsFormView: View {
    @EnvironmentObject var appState: AppState
    @Environment(\.dismiss) private var dismiss

    /// When `true` the form is presented as a sheet from MatchResultsView.
    /// Saving dismisses the sheet instead of pushing a new results screen.
    var isSheet: Bool = false

    @State private var minSqft: Int = 200
    @State private var maxSqft: Int = 600
    @State private var selectedNeighborhoods: Set<String> = []
    @State private var maxMonthlyBudget: Double = 1500
    @State private var leaseStart: Date = Date()
    @State private var leaseDurationMonths: Int = 12
    @State private var openToCoTenants: Bool = false
    @State private var navigateToResults: Bool = false

    private let leaseDurations = [3, 6, 12, 18, 24]
    private let background = Color(red: 0.97, green: 0.96, blue: 0.94)
    private let accent = Color(red: 0.18, green: 0.16, blue: 0.14)

    var body: some View {
        NavigationStack {
            ZStack {
                background.ignoresSafeArea()

                ScrollView {
                    VStack(spacing: 24) {
                        headerSection
                        sqftSection
                        neighborhoodSection
                        budgetSection
                        leaseSection
                        coTenantSection
                        submitButton
                    }
                    .padding(.horizontal, 20)
                    .padding(.vertical, 24)
                }
            }
            .navigationTitle("Studio Needs")
            .navigationBarTitleDisplayMode(.large)
            .toolbar {
                if isSheet {
                    ToolbarItem(placement: .cancellationAction) {
                        Button("Cancel") { dismiss() }
                            .foregroundStyle(accent)
                    }
                }
            }
            .navigationDestination(isPresented: $navigateToResults) {
                MatchResultsView()
                    .environmentObject(appState)
            }
        }
    }

    private var headerSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("What are you looking for?")
                .font(.title2)
                .fontWeight(.bold)
                .foregroundStyle(accent)
            Text("We'll match you with spaces that fit your practice.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    // MARK: - Sqft Section
    private var sqftSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            sectionHeader("Square Footage")

            VStack(spacing: 12) {
                HStack {
                    Text("Min")
                        .font(.caption)
                        .fontWeight(.medium)
                        .foregroundStyle(.secondary)
                        .frame(width: 30, alignment: .leading)

                    Text("\(minSqft) sq ft")
                        .font(.subheadline)
                        .fontWeight(.semibold)
                        .foregroundStyle(accent)
                        .frame(width: 80)

                    Spacer()

                    HStack(spacing: 0) {
                        Button {
                            if minSqft > 100 { minSqft -= 50 }
                        } label: {
                            Image(systemName: "minus")
                                .font(.system(size: 12, weight: .semibold))
                                .frame(width: 36, height: 36)
                                .background(Color.white)
                                .clipShape(RoundedRectangle(cornerRadius: 8))
                                .shadow(color: .black.opacity(0.06), radius: 4, y: 1)
                        }
                        .foregroundStyle(accent)

                        Button {
                            if minSqft < maxSqft - 50 { minSqft += 50 }
                        } label: {
                            Image(systemName: "plus")
                                .font(.system(size: 12, weight: .semibold))
                                .frame(width: 36, height: 36)
                                .background(Color.white)
                                .clipShape(RoundedRectangle(cornerRadius: 8))
                                .shadow(color: .black.opacity(0.06), radius: 4, y: 1)
                        }
                        .foregroundStyle(accent)
                        .padding(.leading, 8)
                    }
                }

                HStack {
                    Text("Max")
                        .font(.caption)
                        .fontWeight(.medium)
                        .foregroundStyle(.secondary)
                        .frame(width: 30, alignment: .leading)

                    Text("\(maxSqft) sq ft")
                        .font(.subheadline)
                        .fontWeight(.semibold)
                        .foregroundStyle(accent)
                        .frame(width: 80)

                    Spacer()

                    HStack(spacing: 0) {
                        Button {
                            if maxSqft > minSqft + 50 { maxSqft -= 50 }
                        } label: {
                            Image(systemName: "minus")
                                .font(.system(size: 12, weight: .semibold))
                                .frame(width: 36, height: 36)
                                .background(Color.white)
                                .clipShape(RoundedRectangle(cornerRadius: 8))
                                .shadow(color: .black.opacity(0.06), radius: 4, y: 1)
                        }
                        .foregroundStyle(accent)

                        Button {
                            if maxSqft < 2000 { maxSqft += 50 }
                        } label: {
                            Image(systemName: "plus")
                                .font(.system(size: 12, weight: .semibold))
                                .frame(width: 36, height: 36)
                                .background(Color.white)
                                .clipShape(RoundedRectangle(cornerRadius: 8))
                                .shadow(color: .black.opacity(0.06), radius: 4, y: 1)
                        }
                        .foregroundStyle(accent)
                        .padding(.leading, 8)
                    }
                }
            }
            .padding(16)
            .background(Color.white)
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .shadow(color: .black.opacity(0.06), radius: 8, y: 2)
        }
    }

    // MARK: - Neighborhood Section
    private var allSelected: Bool {
        selectedNeighborhoods.count == MockData.neighborhoods.count
    }

    private var neighborhoodSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                sectionHeader("Preferred Neighborhoods")
                Spacer()
                Button {
                    if allSelected {
                        selectedNeighborhoods.removeAll()
                    } else {
                        selectedNeighborhoods = Set(MockData.neighborhoods)
                    }
                } label: {
                    Text(allSelected ? "Deselect All" : "Select All")
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .foregroundStyle(accent)
                }
            }
            Text("Select all that interest you. Leave empty to see all.")
                .font(.caption)
                .foregroundStyle(.secondary)

            VStack(spacing: 0) {
                ForEach(Array(MockData.neighborhoods.enumerated()), id: \.element) { index, neighborhood in
                    Button {
                        if selectedNeighborhoods.contains(neighborhood) {
                            selectedNeighborhoods.remove(neighborhood)
                        } else {
                            selectedNeighborhoods.insert(neighborhood)
                        }
                    } label: {
                        HStack {
                            Text(neighborhood)
                                .font(.body)
                                .foregroundStyle(accent)
                            Spacer()
                            if selectedNeighborhoods.contains(neighborhood) {
                                Image(systemName: "checkmark")
                                    .font(.system(size: 13, weight: .semibold))
                                    .foregroundStyle(accent)
                            }
                        }
                        .padding(.horizontal, 16)
                        .padding(.vertical, 12)
                        .background(
                            selectedNeighborhoods.contains(neighborhood)
                            ? accent.opacity(0.06)
                            : Color.white
                        )
                    }

                    if index < MockData.neighborhoods.count - 1 {
                        Divider()
                            .padding(.leading, 16)
                    }
                }
            }
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .shadow(color: .black.opacity(0.06), radius: 8, y: 2)
        }
        .onAppear {
            if let saved = appState.needs {
                selectedNeighborhoods = Set(saved.neighborhoods)
                minSqft = saved.minSqft
                maxSqft = saved.maxSqft
                maxMonthlyBudget = Double(saved.maxMonthlyBudget)
                leaseStart = saved.leaseStart
                leaseDurationMonths = saved.leaseDurationMonths
                openToCoTenants = saved.openToCoTenants
            }
        }
    }

    // MARK: - Budget Section
    private var budgetSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                sectionHeader("Monthly Budget")
                Spacer()
                Text("$\(Int(maxMonthlyBudget))/mo")
                    .font(.headline)
                    .foregroundStyle(accent)
            }

            VStack(spacing: 8) {
                Slider(value: $maxMonthlyBudget, in: 200...5000, step: 100)
                    .tint(accent)

                HStack {
                    Text("$200/mo")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Spacer()
                    Text("$5,000/mo")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            .padding(16)
            .background(Color.white)
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .shadow(color: .black.opacity(0.06), radius: 8, y: 2)
        }
    }

    // MARK: - Lease Section
    private var leaseSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionHeader("Lease Details")

            VStack(spacing: 0) {
                HStack {
                    Text("Lease Start")
                        .font(.body)
                        .foregroundStyle(accent)
                    Spacer()
                    DatePicker("", selection: $leaseStart, displayedComponents: .date)
                        .labelsHidden()
                        .tint(accent)
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 12)

                Divider().padding(.leading, 16)

                HStack {
                    Text("Duration")
                        .font(.body)
                        .foregroundStyle(accent)
                    Spacer()
                    Picker("Duration", selection: $leaseDurationMonths) {
                        ForEach(leaseDurations, id: \.self) { months in
                            Text(months == 1 ? "1 month" : "\(months) months").tag(months)
                        }
                    }
                    .pickerStyle(.menu)
                    .tint(accent)
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 4)
            }
            .background(Color.white)
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .shadow(color: .black.opacity(0.06), radius: 8, y: 2)
        }
    }

    // MARK: - Co-tenant Section
    private var coTenantSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionHeader("Co-Tenants")

            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Open to sharing?")
                        .font(.body)
                        .foregroundStyle(accent)
                    Text("We'll show compatible co-tenant matches.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Toggle("", isOn: $openToCoTenants)
                    .tint(accent)
                    .labelsHidden()
            }
            .padding(16)
            .background(Color.white)
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .shadow(color: .black.opacity(0.06), radius: 8, y: 2)
        }
    }

    // MARK: - Submit
    private var submitButton: some View {
        Button {
            let needs = StudioNeeds(
                minSqft: minSqft,
                maxSqft: maxSqft,
                neighborhoods: Array(selectedNeighborhoods),
                maxMonthlyBudget: Int(maxMonthlyBudget),
                leaseStart: leaseStart,
                leaseDurationMonths: leaseDurationMonths,
                openToCoTenants: openToCoTenants
            )
            appState.saveNeeds(needs)
            if isSheet {
                dismiss()
            } else {
                navigateToResults = true
            }
        } label: {
            Text("Find My Space")
                .font(.headline)
                .foregroundStyle(background)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 18)
                .background(accent)
                .clipShape(RoundedRectangle(cornerRadius: 12))
        }
        .padding(.top, 8)
        .padding(.bottom, 32)
    }

    private func sectionHeader(_ title: String) -> some View {
        Text(title)
            .font(.headline)
            .foregroundStyle(accent)
    }
}

#Preview {
    NeedsFormView()
        .environmentObject(AppState())
}
