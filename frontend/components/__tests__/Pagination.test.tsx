// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import Pagination from "../Pagination";

afterEach(cleanup);

function labels() {
  return screen.getByRole("navigation").textContent;
}

describe("Pagination", () => {
  it("renders nothing for a single page", () => {
    const { container } = render(
      <Pagination currentPage={1} totalPages={1} pathname="/products" searchParams={{}} />
    );
    expect(container.innerHTML).toBe("");
  });

  it("collapses distant pages into ellipses around the current page", () => {
    render(<Pagination currentPage={10} totalPages={20} pathname="/products" searchParams={{}} />);
    expect(labels()).toBe("« Prev1…89101112…20Next »");
    expect(screen.getByText("10").getAttribute("aria-current")).toBe("page");
  });

  it("keeps filters in links, drops the page param on page 1, and skips empty values", () => {
    render(
      <Pagination
        currentPage={2}
        totalPages={3}
        pathname="/products"
        searchParams={{ category: "audio", q: "", page: "2" }}
      />
    );
    expect(screen.getByText("1").getAttribute("href")).toBe("/products?category=audio");
    expect(screen.getByText("3").getAttribute("href")).toBe("/products?category=audio&page=3");
  });

  it("disables Prev on the first page and Next on the last", () => {
    const { rerender } = render(
      <Pagination currentPage={1} totalPages={3} pathname="/p" searchParams={{}} />
    );
    expect(screen.getByText("« Prev").getAttribute("aria-disabled")).toBe("true");
    rerender(<Pagination currentPage={3} totalPages={3} pathname="/p" searchParams={{}} />);
    expect(screen.getByText("Next »").getAttribute("aria-disabled")).toBe("true");
  });
});
