import { Route, BrowserRouter as Router, Routes } from "react-router";
import { ScrollToTop } from "./components/common/ScrollToTop";
import AlternativeLayout from "./layout/AlternativeLayout";
import AppLayout from "./layout/AppLayout";
import AiSettings from "./pages/Ai/AiSettings";
import CodeGeneratorPage from "./pages/Ai/Code/CodeGenerator";
import ImageGeneratorPage from "./pages/Ai/Image/ImageGenerator";
import TextGeneratorPage from "./pages/Ai/Text/TextGenerator";
import VideoGeneratorPage from "./pages/Ai/Video/VideoGenerator";
import ResetPassword from "./pages/AuthPages/ResetPassword";
import SignIn from "./pages/AuthPages/SignIn";
import SignUp from "./pages/AuthPages/SignUp";
import TwoStepVerification from "./pages/AuthPages/TwoStepVerification";
import Calendar from "./pages/Calendar";
import BarChart from "./pages/Charts/BarChart";
import LineChart from "./pages/Charts/LineChart";
import PieChart from "./pages/Charts/PieChart";
import RadarChart from "./pages/Charts/RadarChart";
import RadialChart from "./pages/Charts/RadialChart";
import Chats from "./pages/Chat/Chats";
import AIDashboard from "./pages/Dashboard/AIDashboard";
import Analytics from "./pages/Dashboard/Analytics";
import Crm from "./pages/Dashboard/Crm";
import Ecommerce from "./pages/Dashboard/Ecommerce";
import FinanceDashboard from "./pages/Dashboard/Finance";
import Logistics from "./pages/Dashboard/Logistics";
import Marketing from "./pages/Dashboard/Marketing";
import Saas from "./pages/Dashboard/Saas";
import SalesDashboard from "./pages/Dashboard/Sales";
import Stocks from "./pages/Dashboard/Stocks";
import AddProduct from "./pages/Ecommerce/AddProduct";
import Billing from "./pages/Ecommerce/Billing";
import CreateInvoice from "./pages/Ecommerce/CreateInvoice";
import ProductList from "./pages/Ecommerce/ProductList";
import SingleInvoice from "./pages/Ecommerce/SingleInvoice";
import SingleTransaction from "./pages/Ecommerce/SingleTransaction";
import Transactions from "./pages/Ecommerce/Transactions";
import EmailDetails from "./pages/Email/EmailDetails";
import EmailInbox from "./pages/Email/EmailInbox";
import FormElements from "./pages/Forms/FormElements";
import FormLayout from "./pages/Forms/FormLayout";
import Invoices from "./pages/Invoices";
import LayoutFive from "./pages/Layouts/LayoutFive";
import LayoutFour from "./pages/Layouts/LayoutFour";
import LayoutOne from "./pages/Layouts/LayoutOne";
import LayoutSix from "./pages/Layouts/LayoutSix";
import LayoutThree from "./pages/Layouts/LayoutThree";
import LayoutTwo from "./pages/Layouts/LayoutTwo";
import Maps from "./pages/Maps/Maps";
import VectorMap from "./pages/Maps/VectorMap";
import ApiKeys from "./pages/OtherPage/ApiKeys";
import Blank from "./pages/OtherPage/Blank";
import ComingSoon from "./pages/OtherPage/ComingSoon";
import Faqs from "./pages/OtherPage/Faqs";
import FileManager from "./pages/OtherPage/FileManager";
import FiveZeroThree from "./pages/OtherPage/FiveZeroThree";
import FiveZeroZero from "./pages/OtherPage/FiveZeroZero";
import Integrations from "./pages/OtherPage/Integrations";
import Maintenance from "./pages/OtherPage/Maintenance";
import NotFound from "./pages/OtherPage/NotFound";
import PricingTables from "./pages/OtherPage/PricingTables";
import Success from "./pages/OtherPage/Success";
import TicketList from "./pages/Support/TicketList";
import TicketReply from "./pages/Support/TicketReply";
import BasicTables from "./pages/Tables/BasicTables";
import DataTables from "./pages/Tables/DataTables";
import TaskKanban from "./pages/Task/TaskKanban";
import TaskList from "./pages/Task/TaskList";
import Alerts from "./pages/UiElements/Alerts";
import Avatars from "./pages/UiElements/Avatars";
import Badges from "./pages/UiElements/Badges";
import BreadCrumb from "./pages/UiElements/BreadCrumb";
import Buttons from "./pages/UiElements/Buttons";
import ButtonsGroup from "./pages/UiElements/ButtonsGroup";
import Cards from "./pages/UiElements/Cards";
import Carousel from "./pages/UiElements/Carousel";
import Dropdowns from "./pages/UiElements/Dropdowns";
import Images from "./pages/UiElements/Images";
import Links from "./pages/UiElements/Links";
import Lists from "./pages/UiElements/Lists";
import Modals from "./pages/UiElements/Modals";
import Notifications from "./pages/UiElements/Notifications";
import Pagination from "./pages/UiElements/Pagination";
import Popovers from "./pages/UiElements/Popovers";
import Progressbar from "./pages/UiElements/Progressbar";
import Ribbons from "./pages/UiElements/Ribbons";
import Spinners from "./pages/UiElements/Spinners";
import Tabs from "./pages/UiElements/Tabs";
import Tooltips from "./pages/UiElements/Tooltips";
import Videos from "./pages/UiElements/Videos";
import UserProfiles from "./pages/UserProfiles";

export default function App() {
  return (
    <>
      <Router>
        <ScrollToTop />
        <Routes>
          {/* Dashboard Layout */}
          <Route element={<AppLayout />}>
            <Route index path="/" element={<Ecommerce />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/marketing" element={<Marketing />} />
            <Route path="/crm" element={<Crm />} />
            <Route path="/stocks" element={<Stocks />} />
            <Route path="/saas" element={<Saas />} />
            <Route path="/logistics" element={<Logistics />} />
            <Route path="/sales" element={<SalesDashboard />} />
            <Route path="/ai" element={<AIDashboard />} />
            <Route path="/finance" element={<FinanceDashboard />} />

            <Route path="/calendar" element={<Calendar />} />
            <Route path="/invoice" element={<Invoices />} />
            <Route path="/invoices" element={<Invoices />} />
            <Route path="/chat" element={<Chats />} />
            <Route path="/file-manager" element={<FileManager />} />

            {/* E-commerce */}
            <Route path="/products-list" element={<ProductList />} />
            <Route path="/add-product" element={<AddProduct />} />
            <Route path="/billing" element={<Billing />} />
            <Route path="/single-invoice" element={<SingleInvoice />} />
            <Route path="/create-invoice" element={<CreateInvoice />} />
            <Route path="/transactions" element={<Transactions />} />
            <Route path="/single-transaction" element={<SingleTransaction />} />

            {/* Support */}
            <Route path="/support-tickets" element={<TicketList />} />
            <Route path="/support-ticket-reply" element={<TicketReply />} />

            {/* Others Page */}
            <Route path="/profile" element={<UserProfiles />} />
            <Route path="/faq" element={<Faqs />} />
            <Route path="/pricing-tables" element={<PricingTables />} />
            <Route path="/integrations" element={<Integrations />} />
            <Route path="/api-keys" element={<ApiKeys />} />
            <Route path="/blank" element={<Blank />} />

            {/* Forms */}
            <Route path="/form-elements" element={<FormElements />} />
            <Route path="/form-layout" element={<FormLayout />} />

            {/* Applications */}
            <Route path="/task-list" element={<TaskList />} />
            <Route path="/task-kanban" element={<TaskKanban />} />

            {/* Email */}
            <Route path="/inbox" element={<EmailInbox />} />
            <Route path="/inbox-details" element={<EmailDetails />} />

            {/* Tables */}
            <Route path="/basic-tables" element={<BasicTables />} />
            <Route path="/data-tables" element={<DataTables />} />

            {/* Ui Elements */}
            <Route path="/alerts" element={<Alerts />} />
            <Route path="/avatars" element={<Avatars />} />
            <Route path="/badge" element={<Badges />} />
            <Route path="/breadcrumb" element={<BreadCrumb />} />
            <Route path="/buttons" element={<Buttons />} />
            <Route path="/buttons-group" element={<ButtonsGroup />} />
            <Route path="/cards" element={<Cards />} />
            <Route path="/carousel" element={<Carousel />} />
            <Route path="/dropdowns" element={<Dropdowns />} />
            <Route path="/images" element={<Images />} />
            <Route path="/links" element={<Links />} />
            <Route path="/list" element={<Lists />} />
            <Route path="/modals" element={<Modals />} />
            <Route path="/notifications" element={<Notifications />} />
            <Route path="/pagination" element={<Pagination />} />
            <Route path="/popovers" element={<Popovers />} />
            <Route path="/progress-bar" element={<Progressbar />} />
            <Route path="/ribbons" element={<Ribbons />} />
            <Route path="/spinners" element={<Spinners />} />
            <Route path="/tabs" element={<Tabs />} />
            <Route path="/tooltips" element={<Tooltips />} />
            <Route path="/videos" element={<Videos />} />

            {/* Charts */}
            <Route path="/line-chart" element={<LineChart />} />
            <Route path="/bar-chart" element={<BarChart />} />
            <Route path="/pie-chart" element={<PieChart />} />
            <Route path="/radar-chart" element={<RadarChart />} />
            <Route path="/radial-chart" element={<RadialChart />} />

            {/* Maps */}
            <Route path="/maps" element={<Maps />} />
            <Route path="/vector-map" element={<VectorMap />} />
          </Route>

          {/* Alternative Layout - for special pages */}
          <Route element={<AlternativeLayout />}>
            {/* AI Generator */}
            <Route path="/text-generator" element={<TextGeneratorPage />} />
            <Route path="/image-generator" element={<ImageGeneratorPage />} />
            <Route path="/code-generator" element={<CodeGeneratorPage />} />
            <Route path="/video-generator" element={<VideoGeneratorPage />} />
            <Route path="/ai-settings" element={<AiSettings />} />
          </Route>

          {/* Auth Layout */}
          <Route path="/signin" element={<SignIn />} />
          <Route path="/signup" element={<SignUp />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route
            path="/two-step-verification"
            element={<TwoStepVerification />}
          />

          {/* Layouts */}
          <Route path="/layout-one" element={<LayoutOne />} />
          <Route path="/layout-two" element={<LayoutTwo />} />
          <Route path="/layout-three" element={<LayoutThree />} />
          <Route path="/layout-four" element={<LayoutFour />} />
          <Route path="/layout-five" element={<LayoutFive />} />
          <Route path="/layout-six" element={<LayoutSix />} />

          {/* Fallback Route */}
          <Route path="*" element={<NotFound />} />
          <Route path="/maintenance" element={<Maintenance />} />
          <Route path="/success" element={<Success />} />
          <Route path="/five-zero-zero" element={<FiveZeroZero />} />
          <Route path="/five-zero-three" element={<FiveZeroThree />} />
          <Route path="/coming-soon" element={<ComingSoon />} />
        </Routes>
      </Router>
    </>
  );
}
