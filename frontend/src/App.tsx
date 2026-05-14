import {
  createRouter,
  createRootRoute,
  createRoute,
  RouterProvider,
} from "@tanstack/react-router";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Companies from "./pages/Companies";
import CompanyDetail from "./pages/CompanyDetail";
import Signals from "./pages/Signals";
import Predictions from "./pages/Predictions";
import Articles from "./pages/Articles";
import ArticleReader from "./pages/ArticleReader";
import TrendDetail from "./pages/TrendDetail";
import Reports from "./pages/Reports";
import Tickerbets from "./pages/Tickerbets";

const rootRoute = createRootRoute({ component: Layout });

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: Dashboard,
});

const companiesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/companies",
  component: Companies,
});

const companyDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/companies/$symbol",
  component: CompanyDetail,
});

const signalsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/signals",
  component: Signals,
});

const predictionsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/predictions",
  component: Predictions,
});

const articlesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/articles",
  component: Articles,
});

const articleReaderRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/articles/$articleId",
  component: ArticleReader,
});

const trendDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/trends/$rank",
  component: TrendDetail,
});

const reportsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/reports",
  component: Reports,
});

const tickerbetsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/tickerbets",
  component: Tickerbets,
});

const routeTree = rootRoute.addChildren([
  indexRoute,
  companiesRoute,
  companyDetailRoute,
  signalsRoute,
  predictionsRoute,
  articlesRoute,
  articleReaderRoute,
  trendDetailRoute,
  reportsRoute,
  tickerbetsRoute,
]);

const router = createRouter({
  routeTree,
  basepath: import.meta.env.VITE_BASE || "/",
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

export default function App() {
  return <RouterProvider router={router} />;
}
