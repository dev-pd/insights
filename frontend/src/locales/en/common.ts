export const common = {
  app: {
    title: "Feedback Insights",
    description: "LLM-powered customer feedback extraction and analytics",
  },
  errors: {
    generic: "Something went wrong. Please try again.",
    network: "Could not connect to server.",
    validation: "Input is invalid.",
    notFound: "Page not found",
  },
  loading: {
    generic: "Loading...",
  },
  status: {
    backendOk: "Backend OK",
    backendError: "Backend Error",
    backendChecking: "Checking...",
  },
  actions: {
    tryAgain: "Try again",
    goHome: "Go home",
  },
} as const

export type Common = typeof common
