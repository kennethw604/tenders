export function LogoTitle({ size = "text-2xl" }: { size?: string }) {
  return (
    <div className="flex items-center gap-2 w-full justify-center">
      <p className={`font-bold text-primary ${size}`}>
        <span className="font-light">maple</span>Tenders
      </p>
    </div>
  );
}
