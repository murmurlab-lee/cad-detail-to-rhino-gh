// compile_check/Stubs.cs — Grasshopper/Rhino 最小桩类型集
// 用途: 在无 Rhino 环境下用 dotnet 编译验证脚本体 (模拟 GH 编译环境, LangVersion=5)
// 如脚本体用到更多 API, 在此追加对应桩成员, 签名与 RhinoCommon 保持一致即可。
using System;
using System.Collections.Generic;

namespace Rhino
{
    public class RhinoDoc {}
    namespace Geometry
    {
        public struct BoundingBox
        {
            public BoundingBox(double x0, double y0, double z0, double x1, double y1, double z1) {}
            public BoundingBox(Point3d min, Point3d max) {}
        }
        public struct Point3d
        {
            public Point3d(double x, double y, double z) {}
        }
        public class Brep
        {
            public static Brep CreateFromBox(BoundingBox b) { return new Brep(); }
        }
        public struct Circle
        {
            public Circle(Point3d center, double radius) {}
            public Circle(Plane plane, double radius) {}
        }
        public struct Plane
        {
            public Plane(Point3d origin, Vector3d normal) {}
        }
        public struct Vector3d
        {
            public Vector3d(double x, double y, double z) {}
        }
        public class Cylinder
        {
            public Cylinder(Circle baseCircle, double height) {}
            public Brep ToBrep(bool capBottom, bool capTop) { return new Brep(); }
        }
    }
}

namespace Grasshopper
{
    public class GH_Document {}
    namespace Kernel
    {
        namespace Data {}
        public interface IGH_Component {}
        public static class GH_ScriptComponentUtilities
        {
            public static string ReflectType_CS(object o) { return ""; }
            public static string ReflectType_CS(object o, string m) { return ""; }
        }
        public abstract class GH_ScriptInstance
        {
            protected List<string> __out = new List<string>();
            protected Rhino.RhinoDoc __rhinoDocument;
            protected GH_Document __ghdoc;
            protected IGH_Component __component;
            protected int __iteration;
        }
        namespace Types
        {
            public class GH_Number { public double Value { get; set; } }
            public class GH_Integer { public int Value { get; set; } }
        }
    }
}
