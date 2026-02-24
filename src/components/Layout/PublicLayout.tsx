import { Outlet } from "react-router-dom";
import { useEffect, useState } from "react";
import { UserMenu } from "@/components/auth";
import WindowControls from "@/components/WindowControls";
import { getPlatformService } from "@/service/platform";
import { isElectron } from "@/utils/platform";
import logoHang from "@/assets/logo-hang.svg";

/**
 * PublicLayout - A minimal layout wrapper for public pages (login, signup, pricing)
 * 
 * Provides consistent branding header with logo and auth controls across all public pages.
 * Includes WindowControls for Electron compatibility.
 */
const PublicLayout = () => {
	const [platform, setPlatform] = useState<string>("web");

	useEffect(() => {
		const p = getPlatformService().window.getPlatform();
		setPlatform(p);
	}, []);

	return (
		<div className="h-full flex flex-col relative overflow-hidden">
			{/* Header bar matching TopBar styling */}
			<div
				className="flex !h-9 items-center justify-between px-2 py-1 z-50 border-b border-border/40 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60"
				style={isElectron() ? { WebkitAppRegion: "drag" } as React.CSSProperties : undefined}
			>
				{/* Left side - Logo/Branding */}
				<div 
					className="flex items-center gap-2"
					style={isElectron() ? { WebkitAppRegion: "no-drag" } as React.CSSProperties : undefined}
				>
					{/* macOS window controls space */}
					{platform === "darwin" && <div className="w-[70px]" />}
					
					<img src={logoHang} alt="Hanggent" className="h-5 w-5" />
					<span className="text-sm font-bold text-foreground">hanggent</span>
				</div>

				{/* Right side - Auth controls + Window controls */}
				<div 
					className="flex items-center gap-2"
					style={isElectron() ? { WebkitAppRegion: "no-drag" } as React.CSSProperties : undefined}
				>
					<UserMenu />
					
					{/* Windows/Linux window controls */}
					{platform !== "darwin" && platform !== "web" && (
						<WindowControls />
					)}
				</div>
			</div>

			{/* Page content */}
			<div className="flex-1 overflow-auto">
				<Outlet />
			</div>
		</div>
	);
};

export default PublicLayout;
