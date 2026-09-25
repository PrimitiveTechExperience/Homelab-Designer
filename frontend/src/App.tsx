import { useEffect, useState } from "react";
import { getHealth } from "./api";

type ApiStatus = "checking" | "ok" | "unreachable";

export default function App() {
  const [apiStatus, setApiStatus] = useState<ApiStatus>("checking");

  useEffect(() => {
    getHealth()
      .then(() => setApiStatus("ok"))
      .catch(() => setApiStatus("unreachable"));
  }, []);

  return (
    <main>
      <h1>Homelab Parts Finder</h1>
      <p>Plan server builds, compare used hardware, and estimate 24/7 power cost.</p>
      <p>
        API status: <strong>{apiStatus}</strong>
      </p>
    </main>
  );
}
