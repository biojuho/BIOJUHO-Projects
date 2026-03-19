const Skeleton = ({
  className = '',
  variant = 'text',
  width,
  height,
  rounded = 'lg',
  animate = true,
}) => {
  const variants = {
    text: 'h-4 w-full',
    title: 'h-6 w-3/4',
    avatar: 'h-12 w-12 rounded-full',
    thumbnail: 'h-24 w-24',
    card: 'h-48 w-full',
    button: 'h-10 w-24',
    circle: 'rounded-full',
    rectangular: '',
  };

  const roundedStyles = {
    none: 'rounded-none',
    sm: 'rounded-sm',
    md: 'rounded-md',
    lg: 'rounded-lg',
    xl: 'rounded-xl',
    '2xl': 'rounded-2xl',
    full: 'rounded-full',
  };

  const style = {};
  if (width) style.width = typeof width === 'number' ? `${width}px` : width;
  if (height) style.height = typeof height === 'number' ? `${height}px` : height;

  return (
    <div
      className={[
        'bg-gradient-to-r from-white/65 via-white/35 to-white/65 bg-[length:200%_100%]',
        animate ? 'animate-shimmer' : '',
        variants[variant],
        roundedStyles[rounded],
        className,
      ].join(' ')}
      style={style}
      aria-hidden="true"
      role="presentation"
    />
  );
};

export const SkeletonCard = ({ className = '' }) => (
  <div className={`glass-card space-y-4 p-6 ${className}`}>
    <div className="flex items-start justify-between">
      <Skeleton variant="button" width={80} />
      <Skeleton width={60} />
    </div>
    <Skeleton variant="title" />
    <div className="space-y-2">
      <Skeleton />
      <Skeleton />
      <Skeleton width="60%" />
    </div>
  </div>
);

export const SkeletonTableRow = ({ columns = 4, className = '' }) => (
  <div className={`flex gap-4 py-4 ${className}`}>
    {Array.from({ length: columns }).map((_, index) => (
      <Skeleton key={index} className="flex-1" />
    ))}
  </div>
);

export const SkeletonList = ({ items, count, className = '' }) => {
  const rowCount = count ?? items ?? 3;

  return (
    <div className={`space-y-4 ${className}`}>
      {Array.from({ length: rowCount }).map((_, index) => (
        <div key={index} className="glass-card flex items-center gap-4 p-4">
          <Skeleton variant="avatar" />
          <div className="flex-1 space-y-2">
            <Skeleton variant="title" width="40%" />
            <Skeleton width="70%" />
          </div>
        </div>
      ))}
    </div>
  );
};

export default Skeleton;
