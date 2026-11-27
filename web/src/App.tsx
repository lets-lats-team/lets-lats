import { useEffect, type ComponentType } from 'react';
import { Sprite } from './components/Sprite';
import { Shell } from './components/Shell';
import { Toast } from './components/ui';
import { useRoute, type View } from './lib/router';
import { Landing } from './features/landing/Landing';
import { ProjectsPage } from './features/projects/ProjectsPage';
import { RegisterPage } from './features/register/RegisterPage';
import { LayersPage } from './features/layers/LayersPage';
import { ReviewPage } from './features/review/ReviewPage';
import { PipeTablePage } from './features/table/PipeTablePage';
import { ComparePage } from './features/compare/ComparePage';
import { ExportsPage } from './features/exports/ExportsPage';

const PAGES: Record<View, ComponentType> = {
  projects: ProjectsPage, register: RegisterPage, layers: LayersPage, review: ReviewPage, table: PipeTablePage, compare: ComparePage, exports: ExportsPage,
};

export default function App() {
  const route = useRoute();
  useEffect(() => {
    document.body.style.overflow = route.view ? 'hidden' : '';
  }, [route.view]);
  const Page = route.view ? PAGES[route.view] : null;
  return (
    <>
      <Sprite />
      {route.view && Page ? (
        <Shell view={route.view}>
          <Page />
        </Shell>
      ) : (
        <Landing section={route.section} />
      )}
      <Toast />
    </>
  );
}
