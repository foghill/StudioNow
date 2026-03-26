import SwiftUI

@main
struct StudioNowApp: App {
    @StateObject private var appState = AppState()

    var body: some Scene {
        WindowGroup {
            if appState.profile == nil {
                OnboardingView()
                    .environmentObject(appState)
            } else {
                MainTabView()
                    .environmentObject(appState)
            }
        }
    }
}
