// One neon colour per bug class, shared by the canvas overlay and the UI.
export const CLASS_COLORS = {
  missing_texture: '#FF4D6D',
  texture_glitch: '#FFB020',
  z_fighting: '#A78BFA',
  screen_tear: '#38BDF8',
  uv_stretch: '#34D399',
  color_corruption: '#F472B6',
};

export const classColor = (name) => CLASS_COLORS[name] || '#F87171';
