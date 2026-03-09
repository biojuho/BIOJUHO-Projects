/**
 * Shared i18n message maps for desci-frontend component tests.
 *
 * Centralises the large message objects that were previously duplicated
 * across every test file's vi.mock('LocaleContext') factory.
 *
 * Usage (async vi.mock pattern):
 *   vi.mock('../../contexts/LocaleContext', async () => {
 *     const { LAYOUT_MESSAGES, createLocaleMock } = await import('../mocks/locale-messages.js');
 *     return createLocaleMock(LAYOUT_MESSAGES);
 *   });
 */

// ── Dashboard ──────────────────────────────────────────────────────────────

export const DASHBOARD_MESSAGES = {
  'dashboard.overview': 'Overview',
  'dashboard.welcomeBack': 'Welcome back',
  'dashboard.researcherFallback': 'Researcher',
  'dashboard.networkActive': 'Network Active',
  'dashboard.papersUploaded': 'Papers Uploaded',
  'dashboard.vectorIndex': 'Vector Index',
  'dashboard.pendingReviews': 'Pending Reviews',
  'dashboard.tokenBalance': 'Token Balance',
  'dashboard.statLoading': 'Loading',
  'dashboard.statDocuments': 'Documents',
  'dashboard.statComingSoon': 'Coming soon',
  'dashboard.statIndexed': (v) => `${v.count} indexed`,
  'dashboard.statUploadToStart': 'Upload to start',
  'dashboard.accountStatus': 'Account Status',
  'dashboard.identity': 'Identity',
  'dashboard.email': 'Email',
  'dashboard.provider': 'Provider',
  'dashboard.uid': 'UID',
  'dashboard.systemStatus': 'System Status',
  'dashboard.backendConnectionFailed': 'Backend connection failed',
  'dashboard.node': 'Node',
  'dashboard.online': 'Online',
  'dashboard.role': 'Role',
  'dashboard.rolePrincipalInvestigator': 'Principal Investigator',
  'dashboard.sync': 'Sync',
  'dashboard.automated': 'Automated',
  'dashboard.quickActions': 'Quick Actions',
  'dashboard.quickUploadTitle': 'Upload Paper',
  'dashboard.quickUploadSubtitle': 'Mint IP-NFT',
  'dashboard.quickGrantTitle': 'Find Grants',
  'dashboard.quickGrantSubtitle': 'AI Matching',
  'dashboard.quickVcTitle': 'VC Portal',
  'dashboard.quickVcSubtitle': 'Strategic Partners',
  'dashboard.strategicPartners': 'Strategic VC Partners',
  'dashboard.beta': 'Beta',
};

// ── Layout ─────────────────────────────────────────────────────────────────

export const LAYOUT_MESSAGES = {
  'layout.dashboard': 'Dashboard',
  'layout.biolinker': 'BioLinker',
  'layout.paperUpload': 'Paper Upload',
  'layout.myLab': 'My Lab',
  'layout.notices': 'Notices',
  'layout.vcPortal': 'VC Portal',
  'layout.aiLab': 'AI Lab',
  'layout.peerReview': 'Peer Review',
  'layout.wallet': 'Wallet',
  'layout.closeMenu': 'Close menu',
  'layout.openMenu': 'Open menu',
  'layout.researcher': 'Researcher',
  'layout.signOut': 'Sign Out',
  'layout.signOutAria': 'Sign Out',
  'layout.notifications': 'Notifications',
  'layout.markAllRead': 'Mark all read',
  'layout.viewAllNotifications': 'View all notifications',
  'layout.connectWallet': 'Connect Wallet',
  'layout.walletConnectedTitle': 'Wallet connected',
  'layout.walletConnectedDesc': (v) => `Connected wallet ${v.address ?? ''}`.trim(),
  'layout.walletConnectFailed': 'Wallet connection failed',
};

// ── UploadPaper + AssetManager ─────────────────────────────────────────────

export const UPLOAD_MESSAGES = {
  'uploadPaper.statusPreparing': 'Upload processing...',
  'uploadPaper.validationRequired': 'All required fields must be filled.',
  'uploadPaper.validationTerms': 'Please agree to the copyright and open access policy.',
  'uploadPaper.statusUploading': 'Uploading paper to IPFS...',
  'uploadPaper.statusMinting': 'Minting IP-NFT...',
  'uploadPaper.statusRewarding': 'Distributing DSCI rewards...',
  'uploadPaper.rewardSuccess': ' Rewards delivered.',
  'uploadPaper.rewardDelayed': ' Reward transaction delayed.',
  'uploadPaper.rewardSkipped': ' Reward skipped.',
  'uploadPaper.uploadSuccess': (v) => `Paper uploaded successfully!${v.rewardMessage ?? ''}`,
  'uploadPaper.uploadFailed': 'Upload failed.',
  'uploadPaper.title': 'Research Upload',
  'uploadPaper.subtitle': 'Register a new research paper in the DeSci ecosystem.',
  'uploadPaper.fileDropTitle': 'Click here or drag a PDF file to upload',
  'uploadPaper.fileDropDescription': 'Up to 50MB, PDF only',
  'uploadPaper.titleLabel': 'Paper Title',
  'uploadPaper.titlePlaceholder': 'Ex) A novel approach to targeted CRISPR-Cas9...',
  'uploadPaper.authorsLabel': 'Authors',
  'uploadPaper.authorsPlaceholder': 'Ex) John Doe, Jane Smith (comma separated)',
  'uploadPaper.abstractLabel': 'Abstract',
  'uploadPaper.abstractPlaceholder': 'Summarize the key findings...',
  'uploadPaper.agreementLabel': '[Required] Creative Commons (CC) license and open access agreement',
  'uploadPaper.agreementDescription': 'Agree to permanent open access storage on IPFS.',
  'uploadPaper.submit': 'Store on IPFS and register paper',
  'assetManager.loadFailed': 'Failed to load assets.',
  'assetManager.uploadSuccess': 'Asset uploaded successfully.',
  'assetManager.uploadFailed': 'Failed to upload asset.',
  'assetManager.title': 'Asset Management',
  'assetManager.uploadTitle': 'Upload Company Asset',
  'assetManager.uploadDescription': 'PDF, TXT supported. Max 10MB.',
  'assetManager.selectFile': 'Select File',
  'assetManager.uploading': 'Uploading...',
  'assetManager.myAssets': 'My Assets',
  'assetManager.empty': 'No assets uploaded yet.',
  'assetManager.typeIr': 'IR Deck / Pitch',
  'assetManager.typePaper': 'Technical Paper',
  'assetManager.typePatent': 'Patent Doc',
  'assetManager.typeGeneral': 'Other',
  'assetManager.pinned': 'Pinned',
  'assetManager.pending': 'Pending...',
};

// ── Factory helper ─────────────────────────────────────────────────────────

/**
 * Create a `useLocale` mock from a message map.
 * Handles both plain string values and function values (for interpolation).
 *
 * @param {Record<string, string | ((v: object) => string)>} messages
 */
export function createLocaleMock(messages) {
  return {
    useLocale: () => ({
      t: (key, values = {}) => {
        const entry = messages[key];
        if (typeof entry === 'function') return entry(values);
        return entry || key;
      },
    }),
  };
}
