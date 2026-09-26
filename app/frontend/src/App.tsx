import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import Overview from "./pages/Overview";
import Supporter360 from "./pages/Supporter360";
import Opportunities from "./pages/Opportunities";
import AskArsenal from "./pages/AskArsenal";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Overview />} />
        <Route path="/supporter" element={<Supporter360 />} />
        <Route path="/supporter/:id" element={<Supporter360 />} />
        <Route path="/opportunities" element={<Opportunities />} />
        <Route path="/ask" element={<AskArsenal />} />
      </Routes>
    </Layout>
  );
}
