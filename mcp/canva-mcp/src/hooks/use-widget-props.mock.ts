export function useWidgetProps<T extends Record<string, unknown>>(
  defaultState?: T | (() => T)
): T {
  const mockImage = (
    title: string,
    subtitle: string,
    background: string,
    accent: string
  ) =>
    `data:image/svg+xml;utf8,${encodeURIComponent(`
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 384 280">
        <defs>
          <linearGradient id="bg" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0" stop-color="${background}" />
            <stop offset="1" stop-color="${accent}" />
          </linearGradient>
        </defs>
        <rect width="384" height="280" rx="24" fill="url(#bg)" />
        <rect x="32" y="34" width="320" height="212" rx="18" fill="rgba(255,255,255,0.88)" />
        <rect x="56" y="62" width="112" height="16" rx="8" fill="${accent}" opacity="0.85" />
        <rect x="56" y="100" width="232" height="18" rx="9" fill="#1f2937" opacity="0.92" />
        <rect x="56" y="132" width="188" height="12" rx="6" fill="#4b5563" opacity="0.72" />
        <rect x="56" y="158" width="260" height="12" rx="6" fill="#4b5563" opacity="0.36" />
        <circle cx="296" cy="74" r="30" fill="${background}" opacity="0.72" />
        <text x="56" y="210" font-family="Inter, Arial, sans-serif" font-size="26" font-weight="700" fill="#111827">${title}</text>
        <text x="56" y="234" font-family="Inter, Arial, sans-serif" font-size="15" font-weight="600" fill="#4b5563">${subtitle}</text>
      </svg>
    `)}`;

  const flyerImage = mockImage("Flyer", "Campaign layout", "#00c4cc", "#7d2ae8");
  const presentationImage = mockImage("Deck", "Executive brief", "#2563eb", "#14b8a6");
  const socialImage = mockImage("Social", "Launch post", "#f97316", "#db2777");
  const storyImage = mockImage("Story", "Vertical format", "#111827", "#f59e0b");
  const thumbnailImage = mockImage("Video", "Thumbnail", "#0f766e", "#f43f5e");
  const coverImage = mockImage("Cover", "Audience banner", "#4f46e5", "#22c55e");

  // Mock data for canva widgets
  const mockData = {
    transaction_id: 'tx_abc123def456',
    pages: [
      {
        thumbnail: flyerImage,
        content: [
          { type: 'text', text: 'Welcome to Our Business', value: 'Welcome to Our Business' },
          { type: 'text', text: 'Innovation & Excellence', value: 'Innovation & Excellence' },
        ],
      },
      {
        thumbnail: presentationImage,
        content: [
          { type: 'text', text: 'John Doe', value: 'John Doe' },
          { type: 'text', text: 'CEO & Founder', value: 'CEO & Founder' },
          { type: 'text', text: 'contact@business.com', value: 'contact@business.com' },
        ],
      },
    ],
    content: [
      { type: 'heading', text: 'Main Title', value: 'Main Title' },
      { type: 'body', text: 'Body text content', value: 'Body text content' },
    ],
    query: 'business flyer',
    designs: [
      {
        id: 'design_1',
        title: 'Modern Business Flyer',
        doctype_name: 'Flyer',
        updated_at: '2024-11-01T10:00:00Z',
        thumbnail: {
          url: flyerImage,
        },
        urls: {
          edit_url: 'https://www.canva.com/design/abc123/edit',
          view_url: 'https://www.canva.com/design/abc123/view',
        },
      },
      {
        id: 'design_2',
        title: 'Corporate Presentation',
        doctype_name: 'Presentation',
        updated_at: '2024-10-28T15:30:00Z',
        thumbnail: {
          url: presentationImage,
        },
        urls: {
          edit_url: 'https://www.canva.com/design/def456/edit',
          view_url: 'https://www.canva.com/design/def456/view',
        },
      },
      {
        id: 'design_3',
        title: 'Social Media Post',
        doctype_name: 'Social Media',
        updated_at: '2024-10-25T09:15:00Z',
        thumbnail: {
          url: socialImage,
        },
        urls: {
          edit_url: 'https://www.canva.com/design/ghi789/edit',
          view_url: 'https://www.canva.com/design/ghi789/view',
        },
      },
      {
        id: 'design_4',
        title: 'Instagram Story',
        doctype_name: 'Instagram Story',
        updated_at: '2024-10-20T14:30:00Z',
        thumbnail: {
          url: storyImage,
        },
        urls: {
          edit_url: 'https://www.canva.com/design/jkl012/edit',
          view_url: 'https://www.canva.com/design/jkl012/view',
        },
      },
      {
        id: 'design_5',
        title: 'YouTube Thumbnail',
        doctype_name: 'YouTube',
        updated_at: '2024-10-15T11:45:00Z',
        thumbnail: {
          url: thumbnailImage,
        },
        urls: {
          edit_url: 'https://www.canva.com/design/mno345/edit',
          view_url: 'https://www.canva.com/design/mno345/view',
        },
      },
      {
        id: 'design_6',
        title: 'Facebook Cover',
        doctype_name: 'Facebook',
        updated_at: '2024-10-10T16:20:00Z',
        thumbnail: {
          url: coverImage,
        },
        urls: {
          edit_url: 'https://www.canva.com/design/pqr678/edit',
          view_url: 'https://www.canva.com/design/pqr678/view',
        },
      },
    ],
    candidates: [
      {
        id: 'candidate_1',
        thumbnail_url: flyerImage,
        preview_url: flyerImage,
        url: 'https://www.canva.com/design/abc123/view',
      },
      {
        id: 'candidate_2',
        thumbnail_url: presentationImage,
        preview_url: presentationImage,
        url: 'https://www.canva.com/design/def456/view',
      },
      {
        id: 'candidate_3',
        thumbnail_url: socialImage,
        preview_url: socialImage,
        url: 'https://www.canva.com/design/ghi789/view',
      },
      {
        id: 'candidate_4',
        thumbnail_url: storyImage,
        preview_url: storyImage,
        url: 'https://www.canva.com/design/jkl012/view',
      },
    ],
    job_id: 'job_xyz789',
    continuation: 'next_page_token_xyz',
  };

  return mockData as unknown as T;
}
