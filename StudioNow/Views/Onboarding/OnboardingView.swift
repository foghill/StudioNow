import SwiftUI

struct OnboardingView: View {
    @EnvironmentObject var appState: AppState

    @State private var currentStep: Int = 0
    @State private var name: String = ""
    @State private var discipline: String = "Painting"
    @State private var portfolioURL: String = ""
    @State private var navigateToMain: Bool = false

    private let background = Color(red: 0.97, green: 0.96, blue: 0.94)
    private let accent = Color(red: 0.18, green: 0.16, blue: 0.14)

    var body: some View {
        NavigationStack {
            ZStack {
                background.ignoresSafeArea()

                TabView(selection: $currentStep) {
                    welcomeStep.tag(0)
                    profileStep.tag(1)
                    portfolioStep.tag(2)
                }
                .tabViewStyle(.page(indexDisplayMode: .never))
                .animation(.easeInOut, value: currentStep)
            }
            .navigationDestination(isPresented: $navigateToMain) {
                MainTabView()
                    .environmentObject(appState)
                    .navigationBarBackButtonHidden(true)
            }
        }
    }

    // MARK: - Step Indicator
    private var stepIndicator: some View {
        HStack(spacing: 8) {
            ForEach(0..<3) { index in
                Capsule()
                    .fill(index == currentStep ? accent : accent.opacity(0.2))
                    .frame(width: index == currentStep ? 24 : 8, height: 8)
                    .animation(.spring(response: 0.3), value: currentStep)
            }
        }
    }

    // MARK: - Step 1: Welcome
    private var welcomeStep: some View {
        VStack(spacing: 0) {
            Spacer()

            VStack(spacing: 24) {
                VStack(spacing: 8) {
                    Text("WORTHLESS\nSTUDIOS")
                        .font(.system(size: 13, weight: .medium, design: .monospaced))
                        .tracking(3)
                        .multilineTextAlignment(.center)
                        .foregroundStyle(accent.opacity(0.5))

                    Text("Studio Now")
                        .font(.system(size: 48, weight: .bold))
                        .foregroundStyle(accent)
                }

                Rectangle()
                    .fill(accent.opacity(0.15))
                    .frame(width: 48, height: 2)

                Text("Find your space.\nMake your work.")
                    .font(.title3)
                    .multilineTextAlignment(.center)
                    .foregroundStyle(accent.opacity(0.7))
                    .lineSpacing(4)
            }
            .padding(.horizontal, 20)

            Spacer()

            VStack(spacing: 16) {
                stepIndicator

                Button {
                    withAnimation { currentStep = 1 }
                } label: {
                    Text("Get Started")
                        .font(.headline)
                        .foregroundStyle(background)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 18)
                        .background(accent)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                }

                Text("Free for NYC artists. Always.")
                    .font(.caption)
                    .foregroundStyle(accent.opacity(0.45))
            }
            .padding(.horizontal, 20)
            .padding(.bottom, 48)
        }
    }

    // MARK: - Step 2: Profile
    private var profileStep: some View {
        VStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 8) {
                Text("Tell us about yourself")
                    .font(.title2)
                    .fontWeight(.bold)
                    .foregroundStyle(accent)
                Text("This helps us find spaces that fit your practice.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, 20)
            .padding(.top, 60)

            Spacer()

            VStack(spacing: 20) {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Your name")
                        .font(.caption)
                        .fontWeight(.medium)
                        .foregroundStyle(accent.opacity(0.6))
                        .textCase(.uppercase)
                        .tracking(1)

                    TextField("Full name", text: $name)
                        .font(.body)
                        .padding(16)
                        .background(Color.white)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                        .shadow(color: .black.opacity(0.06), radius: 8, y: 2)
                }

                VStack(alignment: .leading, spacing: 8) {
                    Text("Art discipline")
                        .font(.caption)
                        .fontWeight(.medium)
                        .foregroundStyle(accent.opacity(0.6))
                        .textCase(.uppercase)
                        .tracking(1)

                    Picker("Discipline", selection: $discipline) {
                        ForEach(MockData.disciplines, id: \.self) { d in
                            Text(d).tag(d)
                        }
                    }
                    .pickerStyle(.menu)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(16)
                    .background(Color.white)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                    .shadow(color: .black.opacity(0.06), radius: 8, y: 2)
                }
            }
            .padding(.horizontal, 20)

            Spacer()

            VStack(spacing: 16) {
                stepIndicator

                Button {
                    withAnimation { currentStep = 2 }
                } label: {
                    Text("Continue")
                        .font(.headline)
                        .foregroundStyle(background)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 18)
                        .background(name.trimmingCharacters(in: .whitespaces).isEmpty ? accent.opacity(0.3) : accent)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                }
                .disabled(name.trimmingCharacters(in: .whitespaces).isEmpty)
            }
            .padding(.horizontal, 20)
            .padding(.bottom, 48)
        }
    }

    // MARK: - Step 3: Portfolio
    private var portfolioStep: some View {
        VStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 8) {
                Text("Share your work")
                    .font(.title2)
                    .fontWeight(.bold)
                    .foregroundStyle(accent)
                Text("A portfolio link helps landlords understand your practice. Totally optional.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, 20)
            .padding(.top, 60)

            Spacer()

            VStack(alignment: .leading, spacing: 8) {
                Text("Portfolio URL")
                    .font(.caption)
                    .fontWeight(.medium)
                    .foregroundStyle(accent.opacity(0.6))
                    .textCase(.uppercase)
                    .tracking(1)

                TextField("https://yourwork.com", text: $portfolioURL)
                    .font(.body)
                    .keyboardType(.URL)
                    .autocorrectionDisabled()
                    .textInputAutocapitalization(.never)
                    .padding(16)
                    .background(Color.white)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                    .shadow(color: .black.opacity(0.06), radius: 8, y: 2)

                Text("Optional — Instagram, personal website, or portfolio platform.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .padding(.top, 2)
            }
            .padding(.horizontal, 20)

            Spacer()

            VStack(spacing: 16) {
                stepIndicator

                Button {
                    let profile = ArtistProfile(
                        name: name.trimmingCharacters(in: .whitespaces),
                        discipline: discipline,
                        portfolioURL: portfolioURL.trimmingCharacters(in: .whitespaces).isEmpty ? nil : portfolioURL.trimmingCharacters(in: .whitespaces)
                    )
                    appState.saveProfile(profile)
                    navigateToMain = true
                } label: {
                    Text("Finish Setup")
                        .font(.headline)
                        .foregroundStyle(background)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 18)
                        .background(accent)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                }

                Button {
                    withAnimation { currentStep = 1 }
                } label: {
                    Text("Back")
                        .font(.subheadline)
                        .foregroundStyle(accent.opacity(0.5))
                }
            }
            .padding(.horizontal, 20)
            .padding(.bottom, 48)
        }
    }
}

#Preview {
    OnboardingView()
        .environmentObject(AppState())
}
