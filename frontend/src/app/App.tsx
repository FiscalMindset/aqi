import { Suspense } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nextProvider } from "react-i18next";
import { RouterProvider, createBrowserRouter } from "react-router-dom";
import i18n from "../i18n";
import { routes } from "./routes";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

// React Router must be told the public base path. Served from an API Gateway
// stage (/staging/), the browser URL is /staging/... while the routes are
// defined at /, so without a basename every navigation 404s into the router's
// error boundary ("Unexpected Application Error! 404 Not Found").
const base = import.meta.env.BASE_URL.replace(/\/$/, "");

const router = createBrowserRouter(routes, { basename: base });

export function App() {
  return (
    <I18nextProvider i18n={i18n}>
      <QueryClientProvider client={queryClient}>
        <Suspense fallback={<p className="p-8">Loading…</p>}>
          <RouterProvider router={router} />
        </Suspense>
      </QueryClientProvider>
    </I18nextProvider>
  );
}
