import React from "react";
import "@testing-library/jest-dom/vitest";

// Ensure classic JSX transforms used by some Vitest paths resolve React.
globalThis.React = React;
