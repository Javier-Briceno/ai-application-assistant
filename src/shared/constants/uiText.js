export const UI_TEXT = Object.freeze({
  branding: Object.freeze({
    title: 'Bewerbungsassistent',
    subtitle: 'Job Application Assistant · n8n',
  }),

  input: Object.freeze({
    label: 'Job Posting',
    placeholder:
      'Paste the full job posting here — LinkedIn, StepStone, company website, any format...',
    submitButton: 'Analyze & Generate Package',
  }),

  status: Object.freeze({
    ready: 'Ready',
    analyzing: 'Analyzing posting...',
    success: 'Analysis complete',
    error: 'Something went wrong',
  }),

  emptyState: Object.freeze({
    glyph: '∅',
    message:
      'Paste a job posting on the left and click Analyze. Score, CV edits, and Anschreiben will appear here.',
  }),

  loadingState: Object.freeze({
    glyph: '◌',
    message: 'Searching company · Scoring fit · Generating package — takes ~3 min',
  }),

  errors: Object.freeze({
    emptyPosting: 'Please paste a job posting first.',
    timeout: 'The request took too long. Please try again.',
    network: 'Network error. Please check your connection and try again.',
    generic: 'An unexpected error occurred. Please try again.',
    noProfile: 'Please select a profile before analyzing.',
  }),

  profiles: Object.freeze({
    selectorLabel: 'Active Profile',
    noProfileSelected: '— Select a profile —',
    loadingProfiles: 'Loading profiles...',
    loadError: 'Could not load profiles.',
    createButton: 'New Profile',
    editButton: 'Edit',
    saveButton: 'Save Profile',
    cancelButton: 'Cancel',
    savingButton: 'Saving...',
    createTitle: 'Create Profile',
    editTitle: 'Edit Profile',
    fields: Object.freeze({
      first_name:         'First Name',
      last_name:          'Last Name',
      career_target:      'Career Target',
      cv_text:            'CV Text',
      market_research:    'Market Research',
      email:              'Email',
      phone_country_code: 'Code',
      phone_number:       'Phone Number',
      street_address:     'Street Address',
      postal_code:        'Postal Code',
      city:               'City',
      linkedin_url:       'LinkedIn URL',
      github_url:         'GitHub URL',
    }),
  }),
});