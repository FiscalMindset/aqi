/**
 * MapLibre stub for jsdom.
 *
 * The real library needs WebGL, which jsdom does not provide, so anything that
 * touches the map in a unit test would otherwise pay for a real import and then
 * fail. Playwright drives the real map end to end; this exists so component
 * tests can render the components that CONTAIN a map.
 *
 * It covers the whole surface the app actually calls, because a partial stub
 * turns into a slow test that times out rather than an obvious failure.
 */

export class FakeMap {
  private readonly layers = new Set<string>();
  private readonly sources = new Map<string, unknown>();

  addControl(): this {
    return this;
  }
  remove(): this {
    return this;
  }
  on(): this {
    return this;
  }
  once(): this {
    return this;
  }
  off(): this {
    return this;
  }
  addSource(id: string, source: unknown): this {
    this.sources.set(id, source);
    return this;
  }
  getSource(id: string): unknown {
    if (!this.sources.has(id)) return undefined;
    // A real GeoJSONSource exposes setData; callers use it to refresh data
    // without recreating layers.
    const existing = this.sources.get(id);
    if (typeof existing === "object" && existing !== null) {
      if (!("setData" in existing)) {
        (existing as { setData?: unknown }).setData = (): void => undefined;
      }
      return existing;
    }
    return existing;
  }
  addLayer(layer: { id: string }): this {
    this.layers.add(layer.id);
    return this;
  }
  getLayer(id: string): unknown {
    return this.layers.has(id) ? { id } : undefined;
  }
  removeLayer(id: string): this {
    this.layers.delete(id);
    return this;
  }
  setLayoutProperty(): this {
    return this;
  }
  setPaintProperty(): this {
    return this;
  }
  setData(): this {
    return this;
  }
  getPaintProperty(): unknown {
    return undefined;
  }
  queryRenderedFeatures(): unknown[] {
    return [];
  }
  querySourceFeatures(id: string): unknown[] {
    return this.sources.has(id) ? [{}] : [];
  }
  project(): { x: number; y: number } {
    return { x: 0, y: 0 };
  }
  unproject(): { lng: number; lat: number } {
    return { lng: 0, lat: 0 };
  }
  getCanvas(): { style: { cursor: string } } {
    return { style: { cursor: "" } };
  }
  getContainer(): HTMLElement {
    return document.createElement("div");
  }
  getCenter(): { lng: number; lat: number } {
    return { lng: 0, lat: 0 };
  }
  getZoom(): number {
    return 11;
  }
  getBounds(): object {
    return {};
  }
  loaded(): boolean {
    return true;
  }
  isStyleLoaded(): boolean {
    return true;
  }
  isMoving(): boolean {
    return false;
  }
  flyTo(): this {
    return this;
  }
  easeTo(): this {
    return this;
  }
  jumpTo(): this {
    return this;
  }
  fitBounds(): this {
    return this;
  }
  resize(): this {
    return this;
  }
  triggerRepaint(): this {
    return this;
  }
  setCenter(): this {
    return this;
  }
  setZoom(): this {
    return this;
  }
  addImage(): this {
    return this;
  }
  hasImage(): boolean {
    return false;
  }
}

export class FakePopup {
  setLngLat(): FakePopup {
    return this;
  }
  setHTML(): FakePopup {
    return this;
  }
  setText(): FakePopup {
    return this;
  }
  setDOMContent(): FakePopup {
    return this;
  }
  addClassName(): FakePopup {
    return this;
  }
  addTo(): this {
    return this;
  }
  remove(): this {
    return this;
  }
}

export class FakeMarker {
  setLngLat(): FakeMarker {
    return this;
  }
  addTo(): this {
    return this;
  }
  remove(): this {
    return this;
  }
  getElement(): HTMLElement {
    return document.createElement("div");
  }
}

export const maplibreMock = () => ({
  Map: FakeMap,
  Popup: FakePopup,
  Marker: FakeMarker,
  NavigationControl: class {},
  ScaleControl: class {},
  FullscreenControl: class {},
  AttributionControl: class {},
  LngLatBounds: class {},
  default: {
    Map: FakeMap,
    Popup: FakePopup,
    Marker: FakeMarker,
    NavigationControl: class {},
    ScaleControl: class {},
    FullscreenControl: class {},
  },
});
