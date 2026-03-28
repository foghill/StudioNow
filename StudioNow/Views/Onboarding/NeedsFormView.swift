import SwiftUI

struct NeedsFormView: View {
    @EnvironmentObject var appState: AppState
    @Environment(\.dismiss) private var dismiss

    /// When `true` the form is presented as a sheet from MatchResultsView.
    /// Saving dismisses the sheet instead of pushing a new results screen.
    var isSheet: Bool = false

    @State private var minSqft: Int = 50
    @State private var maxSqft: Int = 10000
    @State private var selectedBoroughs: Set<String> = Set(MockData.boroughs)
    @State private var expandedBoroughs: Set<String> = []
    @State private var maxMonthlyBudget: Double = 5000
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

    /// Variable step size: 50 below 500, 100 up to 2000, 500 above that
    private func sqftStep(for value: Int) -> Int {
        if value < 500 { return 50 }
        if value < 2000 { return 100 }
        return 500
    }

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

                    Text(minSqft == 50 ? "Any" : "\(minSqft) sq ft")
                        .font(.subheadline)
                        .fontWeight(.semibold)
                        .foregroundStyle(accent)
                        .frame(width: 90)

                    Spacer()

                    HStack(spacing: 0) {
                        Button {
                            let step = sqftStep(for: minSqft)
                            if minSqft - step >= 50 { minSqft -= step }
                            else { minSqft = 50 }
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
                            let step = sqftStep(for: minSqft)
                            if minSqft + step < maxSqft { minSqft += step }
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

                    Text(maxSqft >= 10000 ? "Any" : "\(maxSqft) sq ft")
                        .font(.subheadline)
                        .fontWeight(.semibold)
                        .foregroundStyle(accent)
                        .frame(width: 90)

                    Spacer()

                    HStack(spacing: 0) {
                        Button {
                            let step = sqftStep(for: maxSqft)
                            if maxSqft - step > minSqft { maxSqft -= step }
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
                            let step = sqftStep(for: maxSqft)
                            if maxSqft + step <= 10000 { maxSqft += step }
                            else { maxSqft = 10000 }
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

    /// Only the three main boroughs shown by default; Bronx & Staten Island are rare for studios.
    private let primaryBoroughs = ["Manhattan", "Brooklyn", "Queens"]

    private var allBoroughsSelected: Bool {
        primaryBoroughs.allSatisfy { selectedBoroughs.contains($0) }
    }

    private var neighborhoodSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                sectionHeader("Boroughs")
                Spacer()
                Button {
                    if allBoroughsSelected {
                        primaryBoroughs.forEach { selectedBoroughs.remove($0) }
                    } else {
                        primaryBoroughs.forEach { selectedBoroughs.insert($0) }
                    }
                } label: {
                    Text(allBoroughsSelected ? "Deselect All" : "Select All")
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .foregroundStyle(accent)
                }
            }
            Text("All boroughs are selected by default. Deselect to narrow results.")
                .font(.caption)
                .foregroundStyle(.secondary)

            VStack(spacing: 0) {
                ForEach(MockData.neighborhoodsByBorough.filter { primaryBoroughs.contains($0.borough) }, id: \.borough) { group in
                    if group.borough != primaryBoroughs.first {
                        Divider()
                    }

                    // Borough toggle row
                    Button {
                        if selectedBoroughs.contains(group.borough) {
                            selectedBoroughs.remove(group.borough)
                        } else {
                            selectedBoroughs.insert(group.borough)
                        }
                    } label: {
                        HStack {
                            Image(systemName: selectedBoroughs.contains(group.borough) ? "checkmark.circle.fill" : "circle")
                                .font(.system(size: 20))
                                .foregroundStyle(selectedBoroughs.contains(group.borough) ? accent : accent.opacity(0.3))

                            Text(group.borough)
                                .font(.body)
                                .fontWeight(.semibold)
                                .foregroundStyle(accent)

                            Text("(\(group.neighborhoods.count) neighborhoods)")
                                .font(.caption)
                                .foregroundStyle(.secondary)

                            Spacer()

                            // Expand/collapse chevron
                            Button {
                                withAnimation(.easeInOut(duration: 0.2)) {
                                    if expandedBoroughs.contains(group.borough) {
                                        expandedBoroughs.remove(group.borough)
                                    } else {
                                        expandedBoroughs.insert(group.borough)
                                    }
                                }
                            } label: {
                                Image(systemName: expandedBoroughs.contains(group.borough) ? "chevron.up" : "chevron.down")
                                    .font(.system(size: 12, weight: .semibold))
                                    .foregroundStyle(accent.opacity(0.4))
                                    .frame(width: 30, height: 30)
                            }
                        }
                        .padding(.horizontal, 16)
                        .padding(.vertical, 12)
                        .background(
                            selectedBoroughs.contains(group.borough)
                            ? accent.opacity(0.06)
                            : Color.white
                        )
                    }

                    // Collapsible neighborhood list
                    if expandedBoroughs.contains(group.borough) {
                        VStack(spacing: 0) {
                            ForEach(group.neighborhoods, id: \.self) { neighborhood in
                                Divider().padding(.leading, 44)
                                HStack {
                                    Text(neighborhood)
                                        .font(.subheadline)
                                        .foregroundStyle(.secondary)
                                }
                                .padding(.horizontal, 44)
                                .padding(.vertical, 8)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .background(Color.white)
                            }
                        }
                        .transition(.opacity)
                    }
                }
            }
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .shadow(color: .black.opacity(0.06), radius: 8, y: 2)
        }
        .onAppear {
            if let saved = appState.needs {
                // Restore borough selections from saved neighborhoods
                selectedBoroughs = Set(saved.neighborhoods)
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
                neighborhoods: Array(selectedBoroughs),
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
