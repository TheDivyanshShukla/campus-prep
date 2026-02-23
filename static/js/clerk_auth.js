const CONFIG = window.CLERK_CONFIG || {};

const syncClerkSession = async () => {
    try {
        if (!window.Clerk || !window.Clerk.session) return;

        // If already authenticated by Django, skip background sync unless specifically needed
        if (CONFIG.djangoAuthenticated && !window._clerkSyncForced) {
            return;
        }

        // Guard to avoid multiple syncs on the same page load
        if (window._clerkSyncInitiated) return;
        window._clerkSyncInitiated = true;

        const token = await window.Clerk.session.getToken();

        const response = await fetch('/clerk-sync/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token: token })
        });

        const data = await response.json();
        if (data.success && data.redirect_url) {
            const currentPath = window.location.pathname.replace(/\/$/, '') || '/';
            const targetPath = data.redirect_url.replace(/\/$/, '') || '/';

            // 1. Always redirect if onboarding is mandatory and we're not there
            const isMandatoryOnboarding = targetPath === '/onboarding';

            // 2. Only redirect to dashboard if we are currently on an auth page (login/signup/home)
            const isAuthPage = currentPath === '/login' || currentPath === '/signup' || currentPath === '/';

            if ((isMandatoryOnboarding && currentPath !== '/onboarding') || (isAuthPage && currentPath !== targetPath)) {
                window.location.href = data.redirect_url;
            }
        }
    } catch (error) {
        window._clerkSyncInitiated = false;
        console.error('Error syncing Clerk session:', error);
    }
};

const loadClerkSDK = () => {
    if (!CONFIG.publishableKey) return;

    const script = document.createElement('script');
    script.setAttribute('data-clerk-publishable-key', CONFIG.publishableKey);
    script.async = true;
    script.src = `https://${CONFIG.jsUrl}/npm/@clerk/clerk-js@latest/dist/clerk.browser.js`;
    script.crossOrigin = 'anonymous';

    script.addEventListener('load', async () => {
        console.log('Clerk SDK loaded, initializing...');
        await window.Clerk.load();

        // Setup listeners
        window.Clerk.addListener(({ user }) => {
            if (user) syncClerkSession();
        });

        const isDark = document.documentElement.classList.contains('dark');
        const appearance = {
            baseTheme: isDark ? undefined : undefined, // Clerk has built-in themes but we'll use custom styling
            variables: {
                colorPrimary: '#4f46e5',
                colorBackground: isDark ? '#09090b' : '#ffffff',
                colorText: isDark ? '#fafafa' : '#09090b',
                colorInputBackground: isDark ? '#18181b' : '#f4f4f5',
                colorInputText: isDark ? '#fafafa' : '#09090b',
                borderRadius: '0.75rem',
            },
            elements: {
                card: "shadow-none border border-border bg-background",
                headerTitle: "text-foreground font-bold",
                headerSubtitle: "text-muted-foreground",
                socialButtonsBlockButton: "bg-muted border-border hover:bg-muted/80 text-foreground transition-all",
                dividerLine: "bg-border",
                dividerText: "text-muted-foreground",
                formFieldLabel: "text-foreground font-medium",
                formFieldInput: "bg-input border-border text-foreground hover:border-muted-foreground/40 focus:border-primary transition-all",
                formButtonPrimary: "bg-primary text-primary-foreground hover:bg-primary/90 transition-all",
                footerActionText: "text-muted-foreground",
                footerActionLink: "text-primary hover:text-primary/80 transition-all",
                identityPreviewText: "text-foreground",
                identityPreviewEditButton: "text-primary hover:text-primary/80",
                formFieldAction: "text-primary hover:text-primary/80",
            }
        };

        // Initialize UI components if placeholders exist
        const signInDiv = document.getElementById("sign-in");
        if (signInDiv) {
            console.log('Mounting SignIn...');
            window.Clerk.mountSignIn(signInDiv, {
                appearance,
                routing: 'path',
                path: '/login'
            });
        }

        const signUpDiv = document.getElementById("sign-up");
        if (signUpDiv) {
            console.log('Mounting SignUp...');
            window.Clerk.mountSignUp(signUpDiv, {
                appearance,
                routing: 'path',
                path: '/signup'
            });
        }
    });

    script.addEventListener('error', (err) => {
        console.error('Failed to load Clerk SDK. Check your CLERK_PUBLISHable_KEY and CLERK_JS_URL.', err);
    });

    document.head.appendChild(script);
};

if (document.readyState === 'complete') {
    loadClerkSDK();
} else {
    window.addEventListener('load', loadClerkSDK);
}
