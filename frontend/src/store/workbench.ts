import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface GeneratedFile {
  filename: string
  format: string
  title: string
  size: number
  download_url: string
}

export interface Message {
  id: string
  role: 'user' | 'assistant' | 'status'
  content: string
  model?: string
  taskType?: string
  citations?: any[]
  generatedFile?: GeneratedFile
}

export interface Attachment {
  document_id: string
  filename: string
  mime_type: string
}

interface WorkbenchState {
  messages: Message[]
  input: string
  attachments: Attachment[]
  currentModel: string
  currentTask: string
  language: string
  setMessages: (updater: Message[] | ((prev: Message[]) => Message[])) => void
  setInput: (input: string) => void
  setAttachments: (updater: Attachment[] | ((prev: Attachment[]) => Attachment[])) => void
  setCurrentModel: (model: string) => void
  setCurrentTask: (task: string) => void
  setLanguage: (language: string) => void
  clearConversation: () => void
}

/**
 * Chat state (draft input, sent messages, pending attachments) used to
 * live in AIWorkbench's own useState - which meant navigating to any
 * other page unmounted the component and threw all of it away, draft
 * or sent. Moving it into a zustand store keeps it alive across route
 * changes (the store lives outside the component tree), and `persist`
 * additionally keeps it through an accidental page refresh within the
 * same browser tab. isStreaming/isUploading and the messagesEnd ref
 * intentionally stay local to the component - they're per-render UI
 * concerns, not conversation data worth persisting.
 */
export const useWorkbenchStore = create<WorkbenchState>()(
  persist(
    (set) => ({
      messages: [],
      input: '',
      attachments: [],
      currentModel: '',
      currentTask: '',
      language: '',
      setMessages: (updater) => set((state) => ({
        messages: typeof updater === 'function' ? updater(state.messages) : updater,
      })),
      setInput: (input) => set({ input }),
      setAttachments: (updater) => set((state) => ({
        attachments: typeof updater === 'function' ? updater(state.attachments) : updater,
      })),
      setCurrentModel: (model) => set({ currentModel: model }),
      setCurrentTask: (task) => set({ currentTask: task }),
      setLanguage: (language) => set({ language }),
      clearConversation: () => set({ messages: [], input: '', attachments: [] }),
    }),
    {
      name: 'nexa-workbench-session',
      storage: {
        getItem: (name) => {
          const value = sessionStorage.getItem(name)
          return value ? JSON.parse(value) : null
        },
        setItem: (name, value) => sessionStorage.setItem(name, JSON.stringify(value)),
        removeItem: (name) => sessionStorage.removeItem(name),
      },
    }
  )
)
