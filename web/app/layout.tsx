import {
  ClerkProvider,
  SignedIn,
  SignedOut,
  SignInButton,
  UserButton,
} from '@clerk/nextjs';

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ClerkProvider>
      <html lang="en">
        <body style={{ margin: 0, fontFamily: 'system-ui, sans-serif' }}>
          <header
            style={{
              padding: 16,
              borderBottom: '1px solid #eee',
              display: 'flex',
              justifyContent: 'flex-end',
              gap: 12,
            }}
          >
            <SignedOut>
              <SignInButton mode="modal" />
            </SignedOut>
            <SignedIn>
              <UserButton />
            </SignedIn>
          </header>
          {children}
        </body>
      </html>
    </ClerkProvider>
  );
}
