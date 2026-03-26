import SwiftUI

struct MainTabView: View {
    @EnvironmentObject var appState: AppState
    @State private var selectedTab: Int = 0

    private let accent = Color(red: 0.18, green: 0.16, blue: 0.14)

    var body: some View {
        TabView(selection: $selectedTab) {
            // Tab 1: Find Space
            NavigationStack {
                if appState.needs == nil {
                    NeedsFormView()
                        .environmentObject(appState)
                } else {
                    MatchResultsView()
                        .environmentObject(appState)
                }
            }
            .tabItem {
                Label("Find Space", systemImage: "magnifyingglass")
            }
            .tag(0)

            // Tab 2: Dashboard
            NavigationStack {
                DashboardView()
                    .environmentObject(appState)
            }
            .tabItem {
                Label("Dashboard", systemImage: "chart.bar")
            }
            .tag(1)

            // Tab 3: Support
            NavigationStack {
                MediationView()
                    .environmentObject(appState)
            }
            .tabItem {
                Label("Support", systemImage: "bubble.left.and.bubble.right")
            }
            .tag(2)

            // Tab 4: Profile
            NavigationStack {
                ProfileView()
                    .environmentObject(appState)
            }
            .tabItem {
                Label("Profile", systemImage: "person.circle")
            }
            .tag(3)
        }
        .tint(accent)
    }
}

#Preview {
    MainTabView()
        .environmentObject({
            let state = AppState()
            state.saveProfile(ArtistProfile(name: "Jordan Lee", discipline: "Painting", portfolioURL: nil))
            return state
        }())
}
