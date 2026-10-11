import { lazy } from "react";
import type { RouteObject } from "react-router-dom";
import { AppLayout } from "./AppLayout";
import { Loading } from "../components/Loading";

const Explorer = lazy(() => import("../features/explorer/Explorer"));
const RoutesPage = lazy(() => import("../features/routes/RoutesCompare"));
const Subscribe = lazy(() => import("../features/subscribe/Subscribe"));
const HowItWorks = lazy(() => import("../features/howitworks/HowItWorks"));
const Methodology = lazy(() => import("../features/methodology/Methodology"));
const StatusPage = lazy(() => import("../features/status/StatusPage"));

export const routes: RouteObject[] = [
  {
    path: "/",
    element: <AppLayout />,
    children: [
      {
        index: true,
        element: <Loading><Explorer /></Loading>,
      },
      {
        path: "place/:lat/:lon",
        element: <Loading><Explorer /></Loading>,
      },
      { path: "routes", element: <Loading><RoutesPage /></Loading> },
      { path: "subscribe", element: <Loading><Subscribe /></Loading> },
      { path: "how-it-works", element: <Loading><HowItWorks /></Loading> },
      { path: "methodology", element: <Loading><Methodology /></Loading> },
      { path: "status", element: <Loading><StatusPage /></Loading> },
    ],
  },
];
