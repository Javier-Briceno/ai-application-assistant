import { UI_TEXT } from '../shared/constants/uiText.js';

export function initApp() {
    const state = createInitialState();

    return {
        state,

        ui: {
            branding: UI_TEXT.branding,
            input: {
                label: UI_TEXT.input.label,
                placeholder: UI_TEXT.input.placeholder,
                submitText: UI_TEXT.input.submitButton,
            },
            status: {
                text: UI_TEXT.status.ready,
                active: false,
            },
            emptyState: {
                glyph: UI_TEXT.emptyState.glyph,
                text: UI_TEXT.emptyState.message,
            },
            loadingState: {
                glyph: UI_TEXT.loadingState.glyph,
                text: UI_TEXT.loadingState.message,
            },
        },

        registerGlobalListeners({ textarea, onSubmit }) {
            if (!textarea || typeof onSubmit !== 'function') {
                return () => {};
            }

            const handleKeydown = (event) => {
                const isSubmitShortcut =
                event.key === 'Enter' && (event.ctrlKey || event.metaKey);

                if (!isSubmitShortcut) return;

                event.preventDefault();
                onSubmit();
            };

            textarea.addEventListener('keydown', handleKeydown);

            return function cleanup() {
                textarea.removeEventListener('keydown', handleKeydown);
            };
        },
    };
}

function createInitialState() {
    return {
        posting: '',
        isSubmitting: false,
        status: {
            text: UI_TEXT.status.ready,
            active: false,
        },
        view: 'empty', // empty | loading | result | error
        result: null,
        error: null,
        activeProfileId: null,   // number | null
        profiles: [],            // array of { id, full_name, ... }
        profilesLoaded: false,   // true once initial load finished
        profilesError: null,     // string | null
    };
}